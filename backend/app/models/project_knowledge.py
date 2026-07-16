"""Project-scoped source documents and retrieval chunks for formal audits."""

import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base
from .base import SoftDeleteMixin


class ProjectDocument(Base, SoftDeleteMixin):
    """An original project material and its project-isolated parse state."""

    __tablename__ = "project_documents"
    __table_args__ = (
        # The composite key lets chunks enforce that their project matches the
        # owning document instead of relying only on application-side filters.
        UniqueConstraint(
            "id", "project_id", name="uq_project_documents_id_project_id"
        ),
        Index("ix_project_documents_project_status", "project_id", "status"),
        Index("ix_project_documents_project_type", "project_id", "document_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="Owning audit project; project documents are never global",
    )
    title = Column(String(300), nullable=False, comment="Display title")
    document_type = Column(
        String(50), nullable=False, default="other", server_default=text("'other'")
    )
    original_filename = Column(String(500), nullable=False)
    stored_path = Column(String(1000), nullable=False)
    mime_type = Column(String(200))
    file_size = Column(Integer)
    checksum_sha256 = Column(String(64), comment="Original file SHA-256")
    extracted_text = Column(Text, comment="Normalized full text from the parser")
    document_metadata = Column(
        "metadata", JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    status = Column(
        String(20),
        nullable=False,
        default="uploaded",
        server_default=text("'uploaded'"),
        comment="uploaded/parsing/ready/failed/archived",
    )
    parse_error = Column(Text)
    parsed_at = Column(DateTime(timezone=True))
    created_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project = relationship("AuditProject", back_populates="project_documents")
    creator = relationship("User")
    chunks = relationship(
        "ProjectKnowledgeChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="ProjectKnowledgeChunk.chunk_index",
        overlaps="project",
    )

    def __repr__(self):
        return f"<ProjectDocument {self.id}: {self.original_filename}>"


class ProjectKnowledgeChunk(Base):
    """A directly project-scoped retrieval unit from a project document."""

    __tablename__ = "project_knowledge_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "project_id"],
            ["project_documents.id", "project_documents.project_id"],
            name="fk_project_chunks_document_project",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "document_id", "chunk_index", name="uq_project_chunks_document_index"
        ),
        CheckConstraint("chunk_index >= 0", name="ck_project_chunks_index_nonnegative"),
        Index("ix_project_chunks_project_document", "project_id", "document_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="Denormalized mandatory project scope for safe retrieval",
    )
    document_id = Column(UUID(as_uuid=True), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    page_no = Column(Integer)
    section_title = Column(String(500))
    token_count = Column(Integer)
    embedding = Column(Text, comment="JSON-encoded embedding vector")
    embedding_model = Column(String(100))
    chunk_metadata = Column(
        "metadata", JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project = relationship(
        "AuditProject", foreign_keys=[project_id], overlaps="chunks,document"
    )
    document = relationship(
        "ProjectDocument",
        back_populates="chunks",
        foreign_keys=[document_id, project_id],
        overlaps="project",
    )

    def __repr__(self):
        return f"<ProjectKnowledgeChunk {self.document_id}#{self.chunk_index}>"
