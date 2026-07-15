"""Request contracts for the project-scoped audit Agent APIs."""

from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectKnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    top_k: int = Field(5, ge=1, le=20)


class AuditSessionCreateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    plan_item_id: Optional[UUID] = None
    area_record_id: Optional[UUID] = None
    focus: Optional[str] = Field(None, max_length=2000)


class EvidenceSubmitRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=30000)
    evidence_type: Literal["text", "voice", "photo", "document", "mixed"] = "text"
    media_file_ids: list[UUID] = Field(default_factory=list)
    candidate_item_ids: list[UUID] = Field(default_factory=list)
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class DraftOverride(BaseModel):
    draft_id: UUID
    evaluation_3level: Optional[Literal["1", "2", "3"]] = None
    audit_evidence: Optional[str] = None
    audit_findings: Optional[str] = None
    rectification_suggestion: Optional[str] = None


class DraftConfirmRequest(BaseModel):
    draft_ids: list[UUID] = Field(default_factory=list)
    action: Literal["confirm", "reject"] = "confirm"
    safe_only: bool = False
    overrides: list[DraftOverride] = Field(default_factory=list)


class ArtifactGenerateRequest(BaseModel):
    artifact_types: list[
        Literal["area_record", "audit_report", "nc_summary", "manifest", "package"]
    ] = Field(
        default_factory=lambda: [
            "area_record",
            "audit_report",
            "nc_summary",
            "manifest",
        ]
    )
    area_record_id: Optional[UUID] = None
    force: bool = False
