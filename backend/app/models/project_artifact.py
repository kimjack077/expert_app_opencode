"""Versioned downloadable artifacts produced for an audit project."""

import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
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


class ProjectArtifact(Base, SoftDeleteMixin):
    """A generated file with enough metadata for listing and safe download."""

    __tablename__ = "project_artifacts"
    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_project_artifacts_version_positive"),
        UniqueConstraint(
            "project_id",
            "type",
            "filename",
            "version",
            name="uq_project_artifacts_versioned_file",
        ),
        Index("ix_project_artifacts_project_type", "project_id", "type"),
        Index("ix_project_artifacts_project_status", "project_id", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("audit_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_type = Column(
        "type",
        String(50),
        nullable=False,
        comment="area_record/audit_report/nc_summary/package/manifest/other",
    )
    path = Column(String(1000), nullable=False, comment="Server-side storage path")
    filename = Column(String(500), nullable=False, comment="Download filename")
    mime_type = Column(String(200))
    file_size = Column(Integer)
    checksum_sha256 = Column(String(64))
    version = Column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    artifact_metadata = Column(
        "metadata", JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    source_snapshot = Column(
        JSON, nullable=False, default=dict, server_default=text("'{}'::json")
    )
    status = Column(
        String(20),
        nullable=False,
        default="ready",
        server_default=text("'ready'"),
        comment="generating/ready/failed/archived",
    )
    progress = Column(Integer, nullable=False, default=0, server_default=text("0"))
    error_message = Column(Text)
    created_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project = relationship("AuditProject", back_populates="artifacts")
    creator = relationship("User")

    def __repr__(self):
        return (
            f"<ProjectArtifact {self.artifact_type}: "
            f"{self.filename} v{self.version}>"
        )
