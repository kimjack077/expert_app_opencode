"""Project-isolated parsing, indexing and retrieval for formal audits."""

import json
import math
import re
from typing import Any
from uuid import UUID

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
    ) -> dict[str, Any]:
        document.status = "parsing"
        document.parse_error = None
        await db.flush()
        try:
            parsed = project_document_parser.parse(content, document.original_filename)
            document.extracted_text = parsed.text
            document.document_metadata = {
                **(document.document_metadata or {}),
                **parsed.metadata,
            }
            if document.document_type == "auto":
                document.document_type = parsed.metadata.get("category", "other")

            await db.execute(
                delete(ProjectKnowledgeChunk).where(
                    ProjectKnowledgeChunk.document_id == document.id
                )
            )
            chunks = project_document_parser.chunk_text(parsed.text)
            errors: list[str] = []
            for index, chunk_text in enumerate(chunks):
                embedding: list[float] | None = None
                try:
                    embedding = await rag_service._get_document_embedding(chunk_text)
                except Exception as exc:  # lexical fallback remains available
                    errors.append(f"chunk {index}: {type(exc).__name__}")
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
            .where(ProjectKnowledgeChunk.project_id == project_id)
            .options(selectinload(ProjectKnowledgeChunk.document))
        )
        chunks = result.scalars().all()
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
            lexical = len(query_tokens & chunk_tokens) / max(1, len(query_tokens))
            clause_bonus = 0.2 if any(token in chunk.content for token in query_tokens if re.fullmatch(r"\d+(?:\.\d+)+", token)) else 0
            score = semantic * 0.75 + lexical * 0.25 + clause_bonus if query_embedding else lexical + clause_bonus
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
        return combined[:top_k]

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(re.findall(r"\d+(?:\.\d+)+|[A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,}", text.lower()))

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if not left or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        norm_left = math.sqrt(sum(value * value for value in left))
        norm_right = math.sqrt(sum(value * value for value in right))
        return dot / (norm_left * norm_right) if norm_left and norm_right else 0.0


project_knowledge_service = ProjectKnowledgeService()
