"""Formal audit evidence sessions, submissions, atomic evidence and AI drafts."""

import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class AiAuditSession(Base):
    """A persisted AI-assisted work session scoped to one audit project."""

    __tablename__ = "ai_audit_sessions"
    __table_args__ = (
        Index("ix_ai_audit_sessions_project_status", "project_id", "status"),
        Index("ix_ai_audit_sessions_project_creator", "project_id", "created_by"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_conversations.id", ondelete="SET NULL"),
        comment="Optional link to today's persistent conversational agent",
    )
    title = Column(String(300))
    status = Column(
        String(20),
        nullable=False,
        default="active",
        server_default=text("'active'"),
        comment="active/completed/cancelled",
    )
    context_snapshot = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    model_provider = Column(String(100))
    model_name = Column(String(100))
    prompt_version = Column(String(50))
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project = relationship("AuditProject", back_populates="ai_audit_sessions")
    conversation = relationship("AgentConversation")
    creator = relationship("User")
    submissions = relationship(
        "EvidenceSubmission",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    drafts = relationship(
        "AiDraftRecord", back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<AiAuditSession {self.id} project={self.project_id}>"


class EvidenceSubmission(Base):
    """One user submission that may contain several atomic evidence items."""

    __tablename__ = "evidence_submissions"
    __table_args__ = (
        Index("ix_evidence_submissions_project_status", "project_id", "status"),
        Index("ix_evidence_submissions_session", "session_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_audit_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    area_record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_area_records.id", ondelete="SET NULL"),
    )
    plan_item_id = Column(
        UUID(as_uuid=True), ForeignKey("audit_plan_items.id", ondelete="SET NULL")
    )
    submitted_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    input_type = Column(
        String(30),
        nullable=False,
        default="mixed",
        server_default=text("'mixed'"),
        comment="text/photo/document/audio/mixed",
    )
    title = Column(String(300))
    description = Column(Text)
    source_files = Column(
        JSON, nullable=False, default=list, server_default=text("'[]'::json")
    )
    source_snapshot = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        comment="pending/processing/completed/failed",
    )
    error_message = Column(Text)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project = relationship("AuditProject", back_populates="evidence_submissions")
    session = relationship("AiAuditSession", back_populates="submissions")
    area_record = relationship("AuditAreaRecord")
    plan_item = relationship("AuditPlanItem")
    submitter = relationship("User")
    items = relationship(
        "EvidenceItem",
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="EvidenceItem.sequence_no",
    )
    drafts = relationship("AiDraftRecord", back_populates="submission")

    def __repr__(self):
        return f"<EvidenceSubmission {self.id} status={self.status}>"


class EvidenceItem(Base):
    """An atomic, citeable piece of evidence within a submission."""

    __tablename__ = "evidence_items"
    __table_args__ = (
        CheckConstraint("sequence_no >= 0", name="ck_evidence_items_sequence_nonnegative"),
        Index("ix_evidence_items_project_submission", "project_id", "submission_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    submission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("evidence_submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence_no = Column(Integer, nullable=False, default=0, server_default=text("0"))
    evidence_type = Column(
        String(30),
        nullable=False,
        default="text",
        server_default=text("'text'"),
        comment="text/photo/document/audio/observation/interview",
    )
    content = Column(Text, nullable=False)
    file_path = Column(String(1000))
    filename = Column(String(500))
    mime_type = Column(String(200))
    page_no = Column(Integer)
    source_document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project_documents.id", ondelete="SET NULL"),
    )
    source_chunk_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project_knowledge_chunks.id", ondelete="SET NULL"),
    )
    extracted_data = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    item_metadata = Column(
        "metadata", JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    captured_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project = relationship("AuditProject")
    submission = relationship("EvidenceSubmission", back_populates="items")
    source_document = relationship("ProjectDocument")
    source_chunk = relationship("ProjectKnowledgeChunk")

    def __repr__(self):
        return f"<EvidenceItem {self.id} type={self.evidence_type}>"


class AiDraftRecord(Base):
    """A reviewable AI draft that can map one evidence set to many clauses."""

    __tablename__ = "ai_draft_records"
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_ai_draft_records_confidence_range",
        ),
        Index("ix_ai_draft_records_project_status", "project_id", "status"),
        Index("ix_ai_draft_records_session", "session_id"),
        Index("ix_ai_draft_records_submission", "submission_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_audit_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    submission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("evidence_submissions.id", ondelete="SET NULL"),
    )
    area_record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_area_records.id", ondelete="SET NULL"),
    )
    plan_item_id = Column(
        UUID(as_uuid=True), ForeignKey("audit_plan_items.id", ondelete="SET NULL")
    )
    evidence_item_ids = Column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default=text("'{}'")
    )
    # Each entry carries certification_system, clause_no, title and the
    # candidate rank. This preserves one-to-many evidence/clause mapping.
    clause_refs = Column(
        JSON, nullable=False, default=list, server_default=text("'[]'::json")
    )
    primary_clause_no = Column(String(100))
    certification_system = Column(String(20))
    evaluation = Column(
        String(20), comment="conform/minor/major/observation or project policy code"
    )
    finding_text = Column(Text)
    record_payload = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    quality = Column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
        comment="Evidence quality level, score, gaps and attachment checks",
    )
    reasoning = Column(Text, nullable=False)
    confidence = Column(Numeric(5, 4))
    citations = Column(
        JSON, nullable=False, default=list, server_default=text("'[]'::json")
    )
    source_snapshot = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    status = Column(
        String(20),
        nullable=False,
        default="draft",
        server_default=text("'draft'"),
        comment="draft/confirmed/rejected/superseded",
    )
    confirmed_record_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("inspection_record_items.id", ondelete="SET NULL"),
    )
    confirmed_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    confirmed_at = Column(DateTime(timezone=True))
    rejected_reason = Column(Text)
    model_provider = Column(String(100))
    model_name = Column(String(100))
    prompt_version = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project = relationship("AuditProject", back_populates="ai_draft_records")
    session = relationship("AiAuditSession", back_populates="drafts")
    submission = relationship("EvidenceSubmission", back_populates="drafts")
    area_record = relationship("AuditAreaRecord")
    plan_item = relationship("AuditPlanItem")
    confirmed_record_item = relationship("InspectionRecordItem")
    confirmer = relationship("User")
    nonconformities = relationship("Nonconformity", back_populates="source_draft")

    def __repr__(self):
        return f"<AiDraftRecord {self.id} status={self.status}>"
