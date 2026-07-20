"""Request contracts for the project-scoped audit Agent APIs."""

from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class ProjectKnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    top_k: int = Field(5, ge=1, le=20)


class AuditSessionCreateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    plan_item_id: Optional[UUID] = None
    area_record_id: Optional[UUID] = None
    focus: Optional[str] = Field(None, max_length=2000)
    # 已完成任务再次进入时开启新一轮现场审核
    reaudit: bool = False


class EvidenceSubmitRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=30000)
    evidence_type: Literal["text", "voice", "photo", "document", "mixed"] = "text"
    media_file_ids: list[UUID] = Field(default_factory=list)
    candidate_item_ids: list[UUID] = Field(default_factory=list)
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class ManualRecordCreateRequest(BaseModel):
    """A human-authored formal audit record within an active audit session."""

    item_title: str = Field(..., min_length=1, max_length=500)
    clause_nos: list[str] = Field(default_factory=list)
    clause_no: Optional[str] = Field(None, max_length=50)
    certification_system: Literal["Q", "E", "S", "En"]
    evaluation_3level: Literal["1", "2", "3"]
    audit_evidence: str = Field(..., min_length=1, max_length=30000)
    audit_findings: Optional[str] = Field(None, max_length=30000)
    rectification_suggestion: Optional[str] = Field(None, max_length=10000)
    template_item_id: Optional[UUID] = None
    media_file_ids: list[UUID] = Field(default_factory=list)

    @field_validator("clause_nos", mode="before")
    @classmethod
    def normalize_clause_input(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return list(value)

    def resolve_clause_nos(self) -> list[str]:
        resolved: list[str] = []
        for value in [*(self.clause_nos or []), self.clause_no]:
            clause = str(value or "").strip()
            if clause and clause not in resolved:
                resolved.append(clause)
        return resolved

    @model_validator(mode="after")
    def validate_clauses(self):
        clauses = self.resolve_clause_nos()
        if not clauses:
            raise ValueError("clause_nos 或 clause_no 至少填写一项")
        if len(" / ".join(clauses)) > 50:
            raise ValueError("条款号合并后不能超过 50 个字符")
        self.item_title = self.item_title.strip()
        self.audit_evidence = self.audit_evidence.strip()
        self.clause_nos = clauses
        return self


class DraftOverride(BaseModel):
    draft_id: UUID
    evaluation_3level: Optional[Literal["1", "2", "3"]] = None
    audit_evidence: Optional[str] = None
    audit_findings: Optional[str] = None
    rectification_suggestion: Optional[str] = None


class DraftConfirmRequest(BaseModel):
    # P1-6 修复：同时兼容 draft_ids（复数，推荐）与 draft_id（单数，向后兼容）
    draft_ids: list[UUID] = Field(default_factory=list)
    draft_id: Optional[UUID] = None
    action: Literal["confirm", "reject"] = "confirm"
    safe_only: bool = False
    overrides: list[DraftOverride] = Field(default_factory=list)

    def resolve_draft_ids(self) -> list[UUID]:
        """合并 draft_ids 与 draft_id，避免调用方误用单数字段导致 count=0。"""
        ids = list(self.draft_ids or [])
        if self.draft_id and self.draft_id not in ids:
            ids.append(self.draft_id)
        return ids


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
