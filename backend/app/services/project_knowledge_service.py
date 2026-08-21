import asyncio
import json
import math
import re
from functools import partial
from typing import Any
from uuid import UUID

from starlette.concurrency import run_in_threadpool
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project_knowledge import ProjectDocument, ProjectKnowledgeChunk
from app.services.project_document_parser import project_document_parser
from app.services.rag_service import rag_service


class ProjectKnowledgeService:
    async def index_document(
        self,
        db: AsyncSession,
        document: ProjectDocument,
        content: bytes,
        *,
        expected_enterprise_name: str | None = None,
        expected_industry_keywords: list[str] | tuple[str, ...] | None = None,
        force_index: bool = False,
    ) -> dict[str, Any]:
        if bool(getattr(document, "is_deleted", False)):
            raise ValueError("已删除的项目资料不能建立索引")
        document.status = "parsing"
        document.parse_error = None
        await db.flush()
        try:
            # PDF/Word/Excel 解析是同步 CPU 密集操作，必须卸载到线程池，
            # 否则会阻塞事件循环、卡住所有并发请求（含 Agent 的 SSE 流）。
            parsed = await run_in_threadpool(
                project_document_parser.parse, content, document.original_filename
            )
            document.extracted_text = parsed.text
            document.document_metadata = {
                **(document.document_metadata or {}),
                **parsed.metadata,
            }
            consistency = await run_in_threadpool(
                partial(
                    project_document_parser.analyze_consistency,
                    parsed.text,
                    expected_enterprise_name=expected_enterprise_name,
                    expected_industry_keywords=expected_industry_keywords,
                    filename=document.original_filename,
                )
            )
            if document.document_type == "auto":
                document.document_type = parsed.metadata.get("category", "other")

            await db.execute(
                delete(ProjectKnowledgeChunk).where(
                    ProjectKnowledgeChunk.document_id == document.id
                )
            )

            # 如果系统初审发现不一致/隔离风险，且用户未显式确认强制索引
            is_quarantined = bool(consistency.get("recommended_quarantine")) and not force_index
            if is_quarantined:
                document.document_metadata = {
                    **document.document_metadata,
                    "consistency": consistency,
                    "quarantined": True,
                    "searchable": False,
                    "pending_confirmation": True,
                    "warning": consistency["reasons"][0]["message"] if consistency.get("reasons") else "系统初审发现文档与当前项目特征存在偏差，建议仅做归档",
                }
                from sqlalchemy.sql import func

                document.status = "ready"
                document.parsed_at = func.now()
                await db.commit()
                return {
                    "document_id": str(document.id),
                    "chunk_count": 0,
                    "status": document.status,
                    "quarantined": True,
                    "pending_confirmation": True,
                    "requires_confirmation": True,
                    "reasons": consistency.get("reasons", []),
                    "warning": document.document_metadata.get("warning"),
                    "embedding_errors": [],
                }

            # 正常索引或用户显式确认索引
            is_archive_only = bool((document.document_metadata or {}).get("archive_only")) or bool(parsed.metadata.get("archive_only"))
            document.document_metadata = {
                **document.document_metadata,
                "consistency": consistency,
                "quarantined": False,
                "searchable": not is_archive_only,
                "archive_only": is_archive_only,
                "pending_confirmation": False,
                "warning": consistency["reasons"][0]["message"] if consistency.get("reasons") else None,
            }

            # 仅对于未提取出文本的归档类型文件才不分块
            if not parsed.text or not parsed.text.strip():
                from sqlalchemy.sql import func

                document.status = "ready"
                document.parsed_at = func.now()
                await db.commit()
                return {
                    "document_id": str(document.id),
                    "chunk_count": 0,
                    "status": document.status,
                    "archive_only": bool(
                        (document.document_metadata or {}).get("archive_only")
                    ),
                    "warning": (document.document_metadata or {}).get("warning"),
                    "embedding_errors": [],
                }

            chunks = await run_in_threadpool(
                project_document_parser.chunk_text, parsed.text
            )
            errors: list[str] = []
            sem = asyncio.Semaphore(3)

            async def embed_single(idx: int, text: str):
                async with sem:
                    try:
                        emb = await rag_service._get_document_embedding(text)
                        await asyncio.sleep(0.05)
                        return idx, text, emb, None
                    except Exception as exc:
                        return idx, text, None, f"chunk {idx}: {type(exc).__name__}"

            embed_results = await asyncio.gather(
                *(embed_single(i, c) for i, c in enumerate(chunks))
            )

            for index, chunk_text, embedding, err in embed_results:
                if err:
                    errors.append(err)
                db.add(
                    ProjectKnowledgeChunk(
                        project_id=document.project_id,
                        document_id=document.id,
                        chunk_index=index,
                        content=chunk_text,
                        token_count=max(1, len(chunk_text) // 4),
                        embedding=json.dumps(embedding) if embedding else None,
                        embedding_model=rag_service.embedding_model if embedding else None,
                        chunk_metadata={"source": document.original_filename},
                    )
                )
            from sqlalchemy.sql import func

            document.status = "ready"
            document.parsed_at = func.now()
            await db.commit()
            return {
                "document_id": str(document.id),
                "chunk_count": len(chunks),
                "status": document.status,
                "quarantined": False,
                "pending_confirmation": False,
                "requires_confirmation": False,
                "embedding_errors": errors,
            }
        except Exception as exc:
            document.status = "failed"
            document.parse_error = str(exc)
            await db.commit()
            raise

    async def search(
        self,
        db: AsyncSession,
        project_id: UUID,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        result = await db.execute(
            select(ProjectKnowledgeChunk)
            .join(ProjectKnowledgeChunk.document)
            .where(
                ProjectKnowledgeChunk.project_id == project_id,
                ProjectDocument.is_deleted.is_(False),
                ProjectDocument.status == "ready",
            )
            .options(selectinload(ProjectKnowledgeChunk.document))
        )
        chunks = [
            chunk
            for chunk in result.scalars().all()
            if chunk.document and self._document_is_searchable(chunk.document)
        ]
        if not chunks:
            return []

        query_embedding: list[float] | None = None
        try:
            query_embedding = await rag_service._get_embedding(query)
        except Exception:
            query_embedding = None

        query_tokens = self._tokens(query)
        scored: list[tuple[float, ProjectKnowledgeChunk]] = []
        for chunk in chunks:
            semantic = 0.0
            if query_embedding and chunk.embedding:
                try:
                    semantic = self._cosine(query_embedding, json.loads(chunk.embedding))
                except (ValueError, TypeError, json.JSONDecodeError):
                    semantic = 0.0
            chunk_tokens = self._tokens(chunk.content)
            doc_title_tokens = self._tokens(chunk.document.title or "") if chunk.document else set()
            doc_filename_tokens = self._tokens(chunk.document.original_filename or "") if chunk.document else set()
            doc_tokens = doc_title_tokens | doc_filename_tokens

            overlap = query_tokens & (chunk_tokens | doc_tokens)
            lexical = len(overlap) / max(1, len(query_tokens))

            title_overlap = query_tokens & doc_tokens
            title_bonus = 0.15 if len(title_overlap) >= 2 else (0.08 if len(title_overlap) == 1 else 0.0)

            clause_bonus = 0.2 if any(token in chunk.content for token in query_tokens if re.fullmatch(r"\d+(?:\.\d+)+", token)) else 0.0
            if query_embedding:
                score = min(1.0, semantic * 0.7 + lexical * 0.2 + title_bonus + clause_bonus)
            else:
                score = min(1.0, lexical + title_bonus + clause_bonus)
            scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "chunk_id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "document_title": chunk.document.title if chunk.document else "项目资料",
                "file_name": chunk.document.original_filename if chunk.document else None,
                "chunk_index": chunk.chunk_index,
                "page_no": chunk.page_no,
                "content": chunk.content[:1200],
                "similarity": round(float(score), 6),
                "metadata": chunk.chunk_metadata or {},
                "source_scope": "project",
                "project_id": str(project_id),
            }
            for score, chunk in scored[:top_k]
            if score > 0 or len(scored) <= top_k
        ]

    async def search_combined(
        self,
        db: AsyncSession,
        project_id: UUID,
        query: str,
        top_k: int = 8,
    ) -> list[dict[str, Any]]:
        """Search project materials and the global regulation library.

        Project retrieval is always constrained by ``project_id``. Results are
        explicitly labelled so citations preserve their source domain.
        """
        per_scope = max(1, (top_k + 1) // 2)
        project_results = await self.search(db, project_id, query, per_scope)
        global_results = await rag_service.search_knowledge(
            query, db, top_k=per_scope
        )
        scoped_global = [
            {
                **item,
                "source_scope": "global_regulation",
                "project_id": None,
            }
            for item in global_results
        ]

        combined = project_results + scoped_global
        if len(combined) < top_k:
            remaining = top_k - len(combined)
            if len(project_results) < per_scope:
                extra_global = await rag_service.search_knowledge(
                    query, db, top_k=per_scope + remaining
                )
                known = {item.get("chunk_id") for item in scoped_global}
                combined.extend(
                    {
                        **item,
                        "source_scope": "global_regulation",
                        "project_id": None,
                    }
                    for item in extra_global
                    if item.get("chunk_id") not in known
                )
            elif len(scoped_global) < per_scope:
                extra_project = await self.search(
                    db, project_id, query, per_scope + remaining
                )
                known = {item.get("chunk_id") for item in project_results}
                combined.extend(
                    item for item in extra_project if item.get("chunk_id") not in known
                )
        combined.sort(key=lambda x: float(x.get("similarity") or 0.0), reverse=True)
        return combined[:top_k]

    @staticmethod
    def _tokens(text: str) -> set[str]:
        text_clean = text.lower()
        tokens = set()
        # Codes, English words, numbers, standard clauses (e.g. GB/T 19001-2016, 2025, QMS)
        for m in re.finditer(r"\d+(?:\.\d+)+|[a-zA-Z0-9_-]{2,}", text_clean):
            tokens.add(m.group())
        # Chinese characters n-grams (2-grams, 3-grams) and phrases
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", text_clean)
        chinese_text = "".join(chinese_chars)
        for i in range(len(chinese_text) - 1):
            tokens.add(chinese_text[i : i + 2])
            if i + 2 < len(chinese_text):
                tokens.add(chinese_text[i : i + 3])
        for phrase in re.findall(r"[\u4e00-\u9fff]{2,6}", text_clean):
            tokens.add(phrase)
        return tokens

    @classmethod
    def _document_is_searchable(cls, document: ProjectDocument) -> bool:
        metadata = getattr(document, "document_metadata", None) or {}
        return (
            not bool(getattr(document, "is_deleted", False))
            and not bool(metadata.get("archive_only"))
            and metadata.get("searchable", True) is not False
            and not cls._is_quarantined_metadata(metadata)
        )

    @staticmethod
    def _is_quarantined_metadata(metadata: dict[str, Any] | None) -> bool:
        metadata = metadata or {}
        if metadata.get("quarantined") is True:
            return True
        consistency = metadata.get("consistency") or metadata.get(
            "consistency_risk"
        ) or {}
        return bool(
            isinstance(consistency, dict)
            and consistency.get("risk_level") == "high"
            and consistency.get("recommended_quarantine", True)
        )

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if not left or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        norm_left = math.sqrt(sum(value * value for value in left))
        norm_right = math.sqrt(sum(value * value for value in right))
        return dot / (norm_left * norm_right) if norm_left and norm_right else 0.0


project_knowledge_service = ProjectKnowledgeService()
