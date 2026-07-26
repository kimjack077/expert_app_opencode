"""
RAG and Agent Memory Models

This module contains models for:
- Knowledge embeddings (vector storage for RAG)
- Check item regulations (linking check items to knowledge documents)
- Agent memories (persistent memory for AI agents)
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Integer, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from ..database import Base


class KnowledgeEmbedding(Base):
    """Knowledge document embeddings for RAG retrieval"""
    __tablename__ = "knowledge_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        comment="Associated knowledge document"
    )
    chunk_index = Column(Integer, nullable=False, comment="Chunk order in document")
    content = Column(Text, nullable=False, comment="Text content of the chunk")
    embedding = Column(Text, comment="Vector embedding (JSON array or vector type)")
    embedding_model = Column(String(100), comment="Model used for embedding")
    token_count = Column(Integer, comment="Number of tokens in chunk")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    document = relationship("KnowledgeDocument", backref="embeddings")


class CheckItemRegulation(Base):
    """Association table linking template items to knowledge documents"""
    __tablename__ = "check_item_regulations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("template_items.id", ondelete="CASCADE"),
        nullable=False,
        comment="Template item ID"
    )
    knowledge_document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        comment="Knowledge document ID"
    )
    relevance_score = Column(Float, default=0.0, comment="Relevance score from RAG")
    relevant_section = Column(Text, comment="Relevant section/excerpt from document")
    is_auto_linked = Column(Boolean, default=True, comment="Whether this was auto-linked by RAG")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    template_item = relationship("TemplateItem", backref="regulation_links")
    knowledge_document = relationship("KnowledgeDocument", backref="check_item_links")


class AgentMemory(Base):
    """Persistent memory for AI agents"""
    __tablename__ = "agent_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="User ID"
    )
    session_id = Column(UUID(as_uuid=True), comment="Session ID for grouping memories")
    memory_type = Column(
        String(50),
        nullable=False,
        comment="Memory type: preference, experience, context, inspection_pattern"
    )
    content = Column(Text, nullable=False, comment="Memory content")
    embedding = Column(Text, comment="Vector embedding for similarity search")
    importance_score = Column(Float, default=0.5, comment="Importance score (0-1)")
    access_count = Column(Integer, default=0, comment="Number of times accessed")
    last_accessed_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True), comment="Optional expiration time")
    extra_data = Column(Text, comment="Additional metadata (JSON)")
    # 长期记忆作用域（#5）：企业级记忆记录"这家企业反复出现的问题"，
    # 跨会话、跨审核员复用；项目级记忆绑定单个审核项目。均可空。
    enterprise_id = Column(UUID(as_uuid=True), nullable=True, comment="企业级记忆归属企业")
    project_id = Column(UUID(as_uuid=True), nullable=True, comment="项目级记忆归属项目")
    scope = Column(
        String(20), nullable=False, default="user", server_default="user",
        comment="记忆作用域：user/enterprise/project",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    user = relationship("User", backref="agent_memories")


class TemplateRecommendation(Base):
    """Template recommendation history for learning"""
    __tablename__ = "template_recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enterprise_id = Column(
        UUID(as_uuid=True),
        ForeignKey("enterprises.id", ondelete="CASCADE"),
        nullable=False
    )
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("inspection_templates.id", ondelete="CASCADE"),
        nullable=False
    )
    recommendation_score = Column(Float, comment="Recommendation score (0-1)")
    recommendation_reasons = Column(Text, comment="Reasons for recommendation (JSON)")
    was_accepted = Column(Boolean, comment="Whether user accepted the recommendation")
    was_effective = Column(Boolean, comment="Whether the template was effective for inspection")
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    enterprise = relationship("Enterprise", backref="template_recommendations")
    template = relationship("InspectionTemplate", backref="recommendations")


class PhotoAnalysis(Base):
    """Photo analysis results from multimodal LLM"""
    __tablename__ = "photo_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    media_file_id = Column(
        UUID(as_uuid=True),
        ForeignKey("media_files.id", ondelete="CASCADE"),
        nullable=False
    )
    task_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("task_item_records.id", ondelete="SET NULL"),
        comment="Associated task item record"
    )
    analysis_type = Column(
        String(50),
        default="compliance",
        comment="Analysis type: compliance, safety, quality, general"
    )
    detected_issues = Column(Text, comment="Detected issues (JSON array)")
    compliance_status = Column(String(20), comment="Compliance status: compliant, non_compliant, warning")
    confidence_score = Column(Float, comment="Confidence score (0-1)")
    analysis_result = Column(Text, comment="Full analysis text from LLM")
    recommendations = Column(Text, comment="Recommended actions (JSON)")
    model_used = Column(String(100), comment="LLM model used")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    media_file = relationship("MediaFile", backref="analyses")
    task_item = relationship("TaskItemRecord", backref="photo_analyses")