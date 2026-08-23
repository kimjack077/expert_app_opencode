"""
RAG Service for Knowledge Base Retrieval

This service provides:
- Document chunking and embedding generation
- Similarity search for knowledge retrieval
- Auto-linking check items with relevant regulations
"""

import json
import re
from typing import Optional, List, Dict, Any, AsyncGenerator
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.knowledge import KnowledgeDocument
from app.models.template import TemplateItem
from app.models.rag import KnowledgeEmbedding, CheckItemRegulation


# Chunking configuration
CHUNK_SIZE = 500  # Target tokens per chunk
CHUNK_OVERLAP = 50  # Overlap between chunks
SECTION_REFERENCE_PATTERN = re.compile(r"(?<![\d.])(\d+(?:\.\d+)+)(?![\d.])")

# Markdown 标题匹配
_MD_HEADING = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)


class RAGService:
    """Service for RAG-based knowledge retrieval"""

    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            timeout=settings.LLM_TIMEOUT,
        )
        self.model = settings.LLM_MODEL
        # Primary embedding client (BGE-M3 via OpenAI-compatible API)
        self.embedding_client = AsyncOpenAI(
            base_url=settings.EMBEDDING_BASE_URL,
            api_key=settings.EMBEDDING_API_KEY,
            timeout=10,
        )
        self.embedding_model = settings.EMBEDDING_MODEL

    async def create_embeddings_for_document(
        self,
        document_id: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Create embeddings for a knowledge document (batch, non-streaming).
        Returns statistics about the chunking and embedding process.
        """
        result = await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            return {"error": "Document not found"}

        if getattr(document, "is_deleted", False):
            await db.execute(
                delete(KnowledgeEmbedding).where(
                    KnowledgeEmbedding.document_id == document_id
                )
            )
            await db.commit()
            return {"error": "Document is deleted", "embeddings_created": 0}

        if not document.content:
            return {"error": "Document has no content"}

        await db.execute(
            delete(KnowledgeEmbedding).where(KnowledgeEmbedding.document_id == document_id)
        )

        # 优先使用 Markdown 标题层级切块，旧纯文本文档回退到固定大小切块
        source_chunks = self._chunk_markdown(document.content)
        chunks = [
            (chunk_index, chunk)
            for chunk_index, chunk in enumerate(source_chunks)
            if not self._is_table_of_contents_chunk(chunk)
        ]
        toc_chunks_skipped = len(source_chunks) - len(chunks)

        embeddings_created = 0
        errors = []

        for chunk_index, chunk in chunks:
            try:
                embedding = await self._get_document_embedding(chunk)
                kb_embedding = KnowledgeEmbedding(
                    document_id=document_id,
                    chunk_index=chunk_index,
                    content=chunk,
                    embedding=json.dumps(embedding) if embedding else None,
                    embedding_model=self.embedding_model,
                    token_count=self._estimate_tokens(chunk),
                )
                db.add(kb_embedding)
                embeddings_created += 1
            except Exception as e:
                errors.append(f"Chunk {chunk_index}: {str(e)}")

        await db.commit()

        return {
            "document_id": document_id,
            "total_chunks": len(chunks),
            "source_chunks": len(source_chunks),
            "toc_chunks_skipped": toc_chunks_skipped,
            "embeddings_created": embeddings_created,
            "errors": errors,
        }

    async def create_embeddings_streaming(
        self,
        document_id: str,
        db: AsyncSession,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式创建向量索引，逐 chunk 以 AsyncGenerator 推送进度事件。

        事件格式：
          {"stage": "prepare", "message": "..."}             — 准备阶段
          {"stage": "embed",   "current": n, "total": N, "pct": 0~100}  — Embedding 进度
          {"stage": "done",    "document_id": ..., "embeddings_created": n, "errors": [...]}  — 完成
          {"stage": "error",   "message": "..."}            — 致命错误
        """
        result = await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document or getattr(document, "is_deleted", False):
            yield {"stage": "error", "message": "文档不存在或已删除"}
            return

        if not document.content:
            yield {"stage": "error", "message": "文档内容为空，无法建立索引"}
            return

        yield {"stage": "prepare", "message": "正在切分文档章节…"}

        # 清除旧索引
        await db.execute(
            delete(KnowledgeEmbedding).where(KnowledgeEmbedding.document_id == document_id)
        )

        # 按 Markdown 标题层级切块
        source_chunks = self._chunk_markdown(document.content)
        chunks = [
            (idx, chunk)
            for idx, chunk in enumerate(source_chunks)
            if not self._is_table_of_contents_chunk(chunk)
        ]
        total = len(chunks)

        yield {
            "stage": "prepare",
            "message": f"切分完成，共 {total} 个知识片段，开始生成向量索引…",
            "total": total,
        }

        embeddings_created = 0
        errors: List[str] = []

        for n, (chunk_index, chunk) in enumerate(chunks, 1):
            try:
                embedding = await self._get_document_embedding(chunk)
                kb_embedding = KnowledgeEmbedding(
                    document_id=document_id,
                    chunk_index=chunk_index,
                    content=chunk,
                    embedding=json.dumps(embedding) if embedding else None,
                    embedding_model=self.embedding_model,
                    token_count=self._estimate_tokens(chunk),
                )
                db.add(kb_embedding)
                embeddings_created += 1
            except Exception as e:
                errors.append(f"Chunk {chunk_index}: {str(e)}")

            pct = round(n / total * 100) if total else 100
            yield {"stage": "embed", "current": n, "total": total, "pct": pct}

        await db.commit()

        yield {
            "stage": "done",
            "document_id": document_id,
            "embeddings_created": embeddings_created,
            "total_chunks": total,
            "errors": errors,
        }

    async def search_knowledge(
        self,
        query: str,
        db: AsyncSession,
        top_k: int = 5,
        doc_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base using semantic similarity.
        Returns list of relevant document chunks with metadata.
        """
        # Get query embedding
        try:
            query_embedding = await self._get_embedding(query)
        except Exception as e:
            print(f"[RAG] Error getting query embedding: {e}")
            return []

        # Only searchable global knowledge: not soft-deleted, and currently effective.
        # Embeddings for deleted docs may still exist until cleaned up — filter at query time.
        stmt = (
            select(KnowledgeEmbedding)
            .join(
                KnowledgeDocument,
                KnowledgeDocument.id == KnowledgeEmbedding.document_id,
            )
            .where(
                KnowledgeDocument.is_deleted == False,  # noqa: E712
                KnowledgeDocument.status == "effective",
            )
            .options(selectinload(KnowledgeEmbedding.document))
        )

        if doc_type:
            stmt = stmt.where(KnowledgeDocument.doc_type == doc_type)

        result = await db.execute(stmt)
        embeddings = result.scalars().all()

        if not embeddings:
            return []

        # Calculate similarity scores
        scored_chunks = []
        for emb in embeddings:
            doc = emb.document
            if not doc or getattr(doc, "is_deleted", False) or doc.status != "effective":
                continue
            if emb.embedding:
                try:
                    stored_embedding = json.loads(emb.embedding)
                    similarity = self._cosine_similarity(query_embedding, stored_embedding)

                    scored_chunks.append({
                        "chunk_id": str(emb.id),
                        "document_id": str(emb.document_id),
                        "content": emb.content[:500] + "..." if len(emb.content) > 500 else emb.content,
                        "similarity": similarity,
                        "document_title": doc.title,
                        "document_type": doc.doc_type,
                        "chunk_index": emb.chunk_index,
                        "is_table_of_contents": self._is_table_of_contents_chunk(emb.content),
                    })
                except Exception as e:
                    print(f"[RAG] Error processing embedding: {e}")

        # Older documents may have been indexed before TOC filtering was
        # introduced.  Keep query-time protection for those documents, unless
        # the user explicitly asks to see the document's table of contents.
        if not self._is_toc_query(query):
            non_toc_chunks = [
                chunk for chunk in scored_chunks if not chunk["is_table_of_contents"]
            ]
            if non_toc_chunks:
                scored_chunks = non_toc_chunks

        # A PDF table of contents often has a better semantic match for a
        # section number than the section body. When users ask for a specific
        # clause, promote the actual clause text and demote dotted TOC entries.
        section_references = set(SECTION_REFERENCE_PATTERN.findall(query))
        for chunk in scored_chunks:
            rank_score = chunk["similarity"]
            if section_references:
                section_match = self._get_section_match_type(
                    chunk["content"], section_references
                )
                chunk["section_match"] = section_match
                if section_match == "body":
                    rank_score += 1.0
                elif section_match == "toc":
                    rank_score -= 0.25
            chunk["ranking_score"] = rank_score

        # Keep the original similarity for callers that use it as a threshold.
        scored_chunks.sort(key=lambda x: x["ranking_score"], reverse=True)
        return scored_chunks[:top_k]

    @staticmethod
    def _get_section_match_type(content: str, section_references: set[str]) -> Optional[str]:
        """Classify an exact section reference as body text or a TOC entry."""
        for match in SECTION_REFERENCE_PATTERN.finditer(content):
            if match.group(1) not in section_references:
                continue

            following_text = content[match.end():match.end() + 120]
            # A chunk can end immediately after a heading; it is not useful
            # for answering the clause and must not outrank its continuation.
            if len(following_text.strip()) < 24:
                continue
            # TOC lines conventionally contain a title followed by a long run
            # of dots and a page number.  A definition/body heading does not.
            if re.match(r"\s*\S{1,60}\s*(?:\.{4,}|…{2,})", following_text):
                return "toc"
            return "body"
        return None

    @staticmethod
    def _is_table_of_contents_chunk(content: str) -> bool:
        """Return whether a chunk is primarily a dotted-leader table of contents."""
        dot_leaders = re.findall(r"(?:\.{4,}|…{2,})", content)
        if len(dot_leaders) < 2:
            return False

        toc_entries = re.findall(
            r"(?:^|\s)\d+(?:\.\d+)*\s+\S{1,60}\s*(?:\.{4,}|…{2,})\s*\d+",
            content,
        )
        return len(toc_entries) >= 2 or len(dot_leaders) >= 4

    @staticmethod
    def _is_toc_query(query: str) -> bool:
        return bool(re.search(r"目录|章节目录|目录结构|章节列表", query))

    async def link_check_item_to_regulations(
        self,
        template_item_id: str,
        db: AsyncSession,
        top_k: int = 3,
        min_similarity: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Automatically link a check item to relevant regulations.
        Returns list of linked regulations.
        """
        # Fetch template item
        item = await db.get(TemplateItem, template_item_id)
        if not item:
            return []

        # Build search query from item details
        query_parts = [item.title]
        if item.description:
            query_parts.append(item.description)
        if item.legal_basis:
            query_parts.append(item.legal_basis)

        query = " ".join(query_parts)

        # Search for relevant regulations
        results = await self.search_knowledge(query, db, top_k=top_k * 2)

        # Filter by minimum similarity and create links
        linked = []
        for result in results:
            if result["similarity"] >= min_similarity:
                # Check if link already exists
                existing = await db.execute(
                    select(CheckItemRegulation).where(
                        CheckItemRegulation.template_item_id == template_item_id,
                        CheckItemRegulation.knowledge_document_id == result["document_id"],
                    )
                )
                if not existing.scalar_one_or_none():
                    # Create new link
                    link = CheckItemRegulation(
                        template_item_id=template_item_id,
                        knowledge_document_id=result["document_id"],
                        relevance_score=result["similarity"],
                        relevant_section=result["content"],
                        is_auto_linked=True,
                    )
                    db.add(link)
                    linked.append(result)

        await db.commit()
        return linked

    async def get_relevant_regulations_for_item(
        self,
        template_item_id: str,
        db: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """
        Get all relevant regulations for a template item.
        """
        result = await db.execute(
            select(CheckItemRegulation)
            .options(selectinload(CheckItemRegulation.knowledge_document))
            .where(CheckItemRegulation.template_item_id == template_item_id)
            .order_by(CheckItemRegulation.relevance_score.desc())
        )
        links = result.scalars().all()

        regulations = []
        for link in links:
            if link.knowledge_document:
                regulations.append({
                    "id": str(link.id),
                    "document_id": str(link.knowledge_document_id),
                    "document_title": link.knowledge_document.title,
                    "document_type": link.knowledge_document.doc_type,
                    "relevance_score": link.relevance_score,
                    "relevant_section": link.relevant_section,
                    "is_auto_linked": link.is_auto_linked,
                })

        return regulations

    async def generate_regulation_context(
        self,
        query: str,
        db: AsyncSession,
        max_chunks: int = 5,
    ) -> str:
        """
        Generate context string from relevant regulations for LLM prompts.
        """
        results = await self.search_knowledge(query, db, top_k=max_chunks)

        if not results:
            return ""

        context_parts = ["相关法规依据：\n"]
        for i, result in enumerate(results, 1):
            context_parts.append(
                f"{i}. {result['document_title']}（相关度：{result['similarity']:.2f}）\n"
                f"   {result['content'][:200]}...\n"
            )

        return "\n".join(context_parts)

    async def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for query text using OpenAI-compatible API."""
        try:
            # Use OpenAI-compatible embedding API (BGE-M3)
            response = await self.embedding_client.embeddings.create(
                model=self.embedding_model,
                input=[text[:8000]],  # Limit input length
                encoding_format="float"
            )
            return response.data[0].embedding
        except Exception as e:
            # Fallback: use simple embedding
            print(f"[RAG] Embedding API error, using fallback: {e}")
            return self._simple_embedding(text)

    async def _get_document_embedding(self, text: str) -> List[float]:
        """Get embedding for document text using OpenAI-compatible API."""
        try:
            # Use OpenAI-compatible embedding API (BGE-M3)
            response = await self.embedding_client.embeddings.create(
                model=self.embedding_model,
                input=[text[:8000]],  # Limit input length
                encoding_format="float"
            )
            return response.data[0].embedding
        except Exception as e:
            # Fallback: use simple embedding
            print(f"[RAG] Document embedding API error, using fallback: {e}")
            return self._simple_embedding(text)

    def _simple_embedding(self, text: str) -> List[float]:
        """
        Simple fallback embedding using character frequency.
        Not as good as proper embeddings but works for basic similarity.
        """
        # Create a simple hash-based embedding
        import hashlib

        # Use character n-grams
        ngrams = set()
        for i in range(len(text) - 2):
            ngrams.add(text[i:i+3].lower())

        # Create a fixed-size vector (simplified)
        vector = [0.0] * 384
        for ngram in ngrams:
            hash_val = int(hashlib.md5(ngram.encode()).hexdigest()[:8], 16)
            idx = hash_val % 384
            vector[idx] += 1.0

        # Normalize
        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]

        return vector

    def _chunk_markdown(self, text: str) -> List[str]:
        """
        按 Markdown 标题层级切分文档，每个 chunk 头部注入面包屑路径。
        面包屑格式：「> 第1级标题 > 第2级标题 > 当前标题」

        若文档不含任何标题，回退到固定大小切块。
        """
        headings = list(_MD_HEADING.finditer(text))
        if not headings:
            return self._chunk_text(text)

        chunks: List[str] = []
        # 当前各层级标题栈 {level: title}
        breadcrumb: Dict[int, str] = {}

        for i, m in enumerate(headings):
            level = len(m.group(1))  # '#' 数量 = 层级
            title = m.group(2).strip()

            # 更新面包屑：清除比当前层级更深的标题
            for lv in list(breadcrumb.keys()):
                if lv >= level:
                    del breadcrumb[lv]
            breadcrumb[level] = title

            # 本节正文 = 当前标题到下一个同级或更高级标题之间的文字
            start = m.end()
            end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            body = text[start:end].strip()

            if not body:
                continue  # 空节跳过

            # 面包屑字符串
            crumb = " > ".join(breadcrumb[lv] for lv in sorted(breadcrumb))
            header_prefix = f"[{crumb}]\n\n"

            # 若正文过长则进一步切块，每块都加同样的面包屑
            sub_chunks = self._split_by_size(body)
            for sub in sub_chunks:
                chunks.append(header_prefix + sub)

        # 文档开头在第一个标题之前可能有引言文本
        preamble = text[:headings[0].start()].strip() if headings else text.strip()
        if preamble:
            for sub in self._split_by_size(preamble):
                chunks.insert(0, sub)

        return chunks

    def _chunk_text(self, text: str) -> List[str]:
        """
        固定大小切块（兜底，文本无结构时使用）。
        """
        # Clean text
        text = re.sub(r'\s+', ' ', text).strip()

        words = text.split()
        chunks = []
        current_chunk: List[str] = []
        current_length = 0

        for word in words:
            word_len = len(word) + 1
            if current_length + word_len > CHUNK_SIZE and current_chunk:
                chunks.append(' '.join(current_chunk))
                overlap_words = current_chunk[-CHUNK_OVERLAP // 5:]
                current_chunk = overlap_words + [word]
                current_length = sum(len(w) + 1 for w in current_chunk)
            else:
                current_chunk.append(word)
                current_length += word_len

        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks

    def _split_by_size(self, text: str) -> List[str]:
        """将单段文本按 CHUNK_SIZE 切分（供 _chunk_markdown 内部使用）。"""
        if self._estimate_tokens(text) <= CHUNK_SIZE:
            return [text]
        return self._chunk_text(text)

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        # Rough estimate: 1 token ≈ 4 characters for Chinese, 0.75 words for English
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        other_chars = len(text) - chinese_chars
        return chinese_chars + other_chars // 4

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)


rag_service = RAGService()
