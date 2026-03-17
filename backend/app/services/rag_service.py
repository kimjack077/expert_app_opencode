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
            timeout=60,
        )
        self.embedding_model = settings.EMBEDDING_MODEL

    async def create_embeddings_for_document(
        self,
        document_id: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Create embeddings for a knowledge document.
        Returns statistics about the chunking and embedding process.
        """
        # Fetch document
        result = await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        )
        document = result.scalar_one_or_none()

        if not document:
            return {"error": "Document not found"}

        if not document.content:
            return {"error": "Document has no content"}

        # Delete existing embeddings for this document
        await db.execute(
            delete(KnowledgeEmbedding).where(KnowledgeEmbedding.document_id == document_id)
        )

        # Chunk the document
        chunks = self._chunk_text(document.content)

        # Create embeddings for each chunk
        embeddings_created = 0
        errors = []

        for idx, chunk in enumerate(chunks):
            try:
                embedding = await self._get_document_embedding(chunk)

                kb_embedding = KnowledgeEmbedding(
                    document_id=document_id,
                    chunk_index=idx,
                    content=chunk,
                    embedding=json.dumps(embedding) if embedding else None,
                    embedding_model=self.embedding_model,
                    token_count=self._estimate_tokens(chunk),
                )
                db.add(kb_embedding)
                embeddings_created += 1

            except Exception as e:
                errors.append(f"Chunk {idx}: {str(e)}")

        await db.commit()

        return {
            "document_id": document_id,
            "total_chunks": len(chunks),
            "embeddings_created": embeddings_created,
            "errors": errors,
        }

    async def search_knowledge(
        self,
        query: str,
        db: AsyncSession,
        top_k: int = 5,
        category_id: Optional[str] = None,
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

        # Fetch all embeddings (in production, use vector database)
        stmt = select(KnowledgeEmbedding).options(
            selectinload(KnowledgeEmbedding.document)
        )

        if category_id:
            stmt = stmt.join(KnowledgeDocument).where(
                KnowledgeDocument.category_id == category_id
            )

        result = await db.execute(stmt)
        embeddings = result.scalars().all()

        if not embeddings:
            return []

        # Calculate similarity scores
        scored_chunks = []
        for emb in embeddings:
            if emb.embedding:
                try:
                    stored_embedding = json.loads(emb.embedding)
                    similarity = self._cosine_similarity(query_embedding, stored_embedding)

                    scored_chunks.append({
                        "chunk_id": str(emb.id),
                        "document_id": str(emb.document_id),
                        "content": emb.content[:500] + "..." if len(emb.content) > 500 else emb.content,
                        "similarity": similarity,
                        "document_title": emb.document.title if emb.document else "Unknown",
                        "document_type": emb.document.doc_type if emb.document else None,
                        "chunk_index": emb.chunk_index,
                    })
                except Exception as e:
                    print(f"[RAG] Error processing embedding: {e}")

        # Sort by similarity and return top_k
        scored_chunks.sort(key=lambda x: x["similarity"], reverse=True)
        return scored_chunks[:top_k]

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

    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.
        """
        # Clean text
        text = re.sub(r'\s+', ' ', text).strip()

        # Estimate chunk boundaries
        words = text.split()
        chunks = []

        current_chunk = []
        current_length = 0

        for word in words:
            word_len = len(word) + 1  # +1 for space
            if current_length + word_len > CHUNK_SIZE and current_chunk:
                # Save current chunk
                chunks.append(' '.join(current_chunk))

                # Start new chunk with overlap
                overlap_words = current_chunk[-CHUNK_OVERLAP // 5:]  # Approximate overlap
                current_chunk = overlap_words + [word]
                current_length = sum(len(w) + 1 for w in current_chunk)
            else:
                current_chunk.append(word)
                current_length += word_len

        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks

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