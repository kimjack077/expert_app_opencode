"""Completeness checks and versioned project deliverables."""

import hashlib
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from docx import Document
from sqlalchemy import func, select
from starlette.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.audit_project import (
    AuditAreaRecord,
    AuditPlanItem,
    AuditProject,
    AuditReport,
    AuditTeamMember,
    CommunicationMeeting,
    Nonconformity,
)
from app.models.evidence_agent import AiDraftRecord
from app.models.project_artifact import ProjectArtifact
from app.models.project_knowledge import ProjectDocument
from app.services.report_generator import generate_audit_report_word
from app.utils.storage_path import resolve_storage_path, storage_key


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\r\n]+", "_", value).strip(" .")
    return cleaned[:180] or "artifact"


class ProjectArtifactService:
    async def source_snapshot(self, db: AsyncSession, project_id: UUID) -> dict[str, Any]:
        project = await db.get(AuditProject, project_id)
        if not project:
            raise ValueError("审核项目不存在")
        plan_items = (
            await db.execute(
                select(AuditPlanItem).where(
                    AuditPlanItem.project_id == project_id,
                    AuditPlanItem.is_deleted.is_(False),
                )
            )
        ).scalars().all()
        team_members = (
            await db.execute(
                select(AuditTeamMember)
                .where(
                    AuditTeamMember.project_id == project_id,
                    AuditTeamMember.is_deleted.is_(False),
                )
                .options(selectinload(AuditTeamMember.member))
            )
        ).scalars().all()
        records = (
            await db.execute(
                select(AuditAreaRecord)
                .where(AuditAreaRecord.project_id == project_id)
                .options(
                    selectinload(AuditAreaRecord.items),
                    selectinload(AuditAreaRecord.area),
                    selectinload(AuditAreaRecord.plan_item),
                )
            )
        ).scalars().all()
        ncs = (await db.execute(select(Nonconformity).where(Nonconformity.project_id == project_id))).scalars().all()
        drafts = (await db.execute(select(AiDraftRecord).where(AiDraftRecord.project_id == project_id))).scalars().all()
        meetings = (
            await db.execute(
                select(CommunicationMeeting).where(
                    CommunicationMeeting.project_id == project_id
                )
            )
        ).scalars().all()
        reports = (
            await db.execute(
                select(AuditReport).where(AuditReport.project_id == project_id)
            )
        ).scalars().all()
        documents = (
            await db.execute(self._active_documents_statement(project_id))
        ).scalars().all()
        auditor_names = {
            str(item.member_id): self._member_display_name(item.member)
            for item in team_members
        }
        return {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "project": {
                "id": str(project.id),
                "project_no": project.project_no,
                "title": project.title,
                "status": project.status,
                "audit_type": project.audit_type,
                "certification_systems": project.certification_systems or [],
                "scheduled_start": self._iso_value(project.scheduled_start),
                "scheduled_end": self._iso_value(project.scheduled_end),
                "actual_start": self._iso_value(project.actual_start),
                "actual_end": self._iso_value(project.actual_end),
            },
            "auditors": [
                {
                    "id": str(item.member_id),
                    "name": self._member_display_name(item.member),
                    "role": item.role,
                    "certification_systems": item.responsible_systems or [],
                    "qualification_codes": item.qualification_codes or [],
                    "registration_no": item.registration_no,
                    "registration_level": item.registration_level,
                    "assigned_areas": item.assigned_areas or [],
                    "assigned_clauses": item.assigned_clauses or [],
                    "status": item.status,
                }
                for item in team_members
            ],
            "plan_items": [
                {
                    "id": str(item.id),
                    "date": self._iso_value(item.plan_date),
                    "time_start": item.time_start,
                    "time_end": item.time_end,
                    "group": item.group_no,
                    "area": item.area_name,
                    "area_type": item.area_type,
                    "activity_type": item.activity_type,
                    "status": item.status,
                    "certification_systems": item.certification_systems or [],
                    "clauses": item.clauses or [],
                    "assigned_auditor_ids": [
                        str(value) for value in (item.assigned_member_ids or [])
                    ],
                    "assigned_auditors": [
                        {
                            "id": str(value),
                            "name": auditor_names.get(str(value), str(value)),
                        }
                        for value in (item.assigned_member_ids or [])
                    ],
                    "is_joint": bool(item.is_joint),
                    "joint_groups": item.joint_group_ids or [],
                }
                for item in plan_items
            ],
            "area_records": [
                {
                    "id": str(record.id),
                    "plan_item_id": str(record.plan_item_id) if record.plan_item_id else None,
                    "area": self._area_name(record),
                    "status": record.status,
                    "audit_date": self._iso_value(record.audit_date),
                    "time_start": record.audit_time_start,
                    "time_end": record.audit_time_end,
                    "certification_systems": record.certification_systems or [],
                    "recorded_by": str(record.recorded_by),
                    "co_recorders": [str(value) for value in (record.co_recorders or [])],
                    "conclusion": record.conclusion or "",
                    "items": [
                        {
                            "id": str(item.id),
                            "template_item_id": str(item.template_item_id) if item.template_item_id else None,
                            "title": item.item_title,
                            "clause_no": item.clause_no_snapshot,
                            "certification_system": item.certification_system,
                            "evaluation": item.evaluation_3level,
                            "evidence": item.audit_evidence,
                            "findings": item.audit_findings,
                            "photos": item.photos or [],
                            "ai_generated": bool(item.ai_generated),
                            "ai_reasoning": item.ai_suggestion,
                            "ai_basis": item.ai_basis,
                        }
                        for item in record.items
                    ],
                }
                for record in records
            ],
            "nonconformities": [{"id": str(item.id), "number": item.nc_no, "status": item.status, "severity": item.severity, "clause": item.clause_no} for item in ncs],
            "meetings": [
                {
                    "id": str(item.id),
                    "type": item.meeting_type,
                    "time": self._iso_value(item.meeting_time),
                    "participants_enterprise": item.participants_enterprise or "",
                    "audit_team_member_ids": [
                        str(value) for value in (item.participants_audit_team or [])
                    ],
                    "audit_team_members": [
                        auditor_names.get(str(value), str(value))
                        for value in (item.participants_audit_team or [])
                    ],
                    "key_points": item.key_points or "",
                    "minutes": item.meeting_minutes or "",
                    "sign_in_sheet": item.sign_in_sheet or {},
                }
                for item in meetings
            ],
            "reports": [
                {
                    "id": str(item.id),
                    "type": item.report_type,
                    "number": item.report_no,
                    "version": item.version,
                    "status": (
                        "approved"
                        if item.approved_at
                        else "reviewed"
                        if item.reviewed_at
                        else "draft"
                    ),
                    "conclusion": item.conclusion,
                }
                for item in reports
            ],
            "drafts": [
                {
                    "id": str(item.id),
                    "session_id": str(item.session_id),
                    "submission_id": str(item.submission_id) if item.submission_id else None,
                    "area_record_id": str(item.area_record_id) if item.area_record_id else None,
                    "plan_item_id": str(item.plan_item_id) if item.plan_item_id else None,
                    "status": item.status,
                    "clause": item.primary_clause_no,
                    "clause_refs": item.clause_refs or [],
                    "evaluation": item.evaluation,
                    "quality": item.quality or {},
                    "reasoning": item.reasoning,
                    "confidence": float(item.confidence or 0),
                    "citations": item.citations or [],
                    "model_name": item.model_name,
                    "prompt_version": item.prompt_version,
                }
                for item in drafts
            ],
            "documents": [
                {
                    "id": str(item.id),
                    "name": item.original_filename,
                    "status": item.status,
                    "type": item.document_type,
                    "metadata": item.document_metadata or {},
                }
                for item in documents
            ],
        }

    async def quality_check(self, db: AsyncSession, project_id: UUID) -> dict[str, Any]:
        snapshot = await self.source_snapshot(db, project_id)
        return self.evaluate_snapshot_quality(snapshot)

    @classmethod
    def evaluate_snapshot_quality(cls, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Evaluate formal-output readiness without database side effects."""

        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        plan_items = list(snapshot.get("plan_items") or [])
        records = list(snapshot.get("area_records") or [])
        drafts = list(snapshot.get("drafts") or [])
        ncs = list(snapshot.get("nonconformities") or [])
        documents = list(snapshot.get("documents") or [])
        meetings = list(snapshot.get("meetings") or [])
        reports = list(snapshot.get("reports") or [])

        quarantined_documents = [
            item
            for item in documents
            if cls._is_quarantined_metadata(item.get("metadata"))
        ]
        active_documents = [
            item for item in documents if item not in quarantined_documents
        ]
        archive_only_documents = [
            item
            for item in active_documents
            if (item.get("metadata") or {}).get("archive_only")
        ]
        failed_documents = [
            item for item in active_documents if item.get("status") == "failed"
        ]
        incomplete_plans = [
            item for item in plan_items if item.get("status") != "completed"
        ]
        unsubmitted_records = [
            item
            for item in records
            if item.get("status") not in {"submitted", "reviewed"}
        ]
        submitted_records = [
            item
            for item in records
            if item.get("status") in {"submitted", "reviewed"}
        ]
        empty_submitted_records = [
            record
            for record in submitted_records
            if not any(
                cls._is_valid_record_item(item)
                for item in (record.get("items") or [])
            )
        ]
        pending_drafts = [
            item for item in drafts if item.get("status") == "draft"
        ]
        unclosed_ncs = [item for item in ncs if not cls._is_nc_closed(item)]

        planned_clauses = {
            clause
            for plan in plan_items
            for clause in cls._clause_tokens(plan.get("clauses") or [])
        }
        recorded_clauses = {
            clause
            for record in submitted_records
            for item in (record.get("items") or [])
            if cls._is_valid_record_item(item)
            for clause in cls._clause_tokens(item.get("clause_no"))
        }
        covered_clauses = planned_clauses & recorded_clauses
        uncovered_clauses = sorted(planned_clauses - recorded_clauses)
        clause_coverage = round(
            len(covered_clauses) / len(planned_clauses) * 100, 2
        ) if planned_clauses else 100.0

        opening_meetings = [
            item
            for item in meetings
            if str(item.get("type") or "").lower()
            in {"opening", "opening_meeting"}
        ]
        closing_meetings = [
            item
            for item in meetings
            if str(item.get("type") or "").lower()
            in {"closing", "closing_meeting"}
        ]
        sign_in_document = any(
            "签到" in str(item.get("name") or "") for item in active_documents
        )
        meeting_sign_in = sign_in_document or (
            any(cls._has_content(item.get("sign_in_sheet")) for item in opening_meetings)
            and any(
                cls._has_content(item.get("sign_in_sheet"))
                for item in closing_meetings
            )
        )

        management_documents = [
            item
            for item in active_documents
            if str(item.get("type") or "").lower() in {"manual", "procedure"}
            or str((item.get("metadata") or {}).get("category") or "").lower()
            in {"manual", "procedure"}
            or any(
                keyword in str(item.get("name") or "")
                for keyword in ("管理手册", "程序文件")
            )
        ]
        valid_records = bool(records) and not unsubmitted_records and not empty_submitted_records
        archive_checks = {
            "A_organization_materials": bool(active_documents),
            "B_audit_plan": bool(plan_items) and not incomplete_plans,
            "C_management_documents": bool(management_documents),
            "D_opening_closing_meetings_and_sign_in": bool(opening_meetings)
            and bool(closing_meetings)
            and meeting_sign_in,
            "E_area_records": valid_records,
            "F_audit_report": bool(reports),
            "G_nonconformity_closure": not unclosed_ncs,
            "I_document_manifest": bool(active_documents),
        }
        archive_completeness_score = round(
            sum(1 for passed in archive_checks.values() if passed)
            / len(archive_checks)
            * 100
        )
        archive_ready = all(archive_checks.values())

        if not records:
            blockers.append(
                {"code": "NO_AREA_RECORD", "message": "尚未形成任何区域审核记录"}
            )
        if not plan_items:
            blockers.append(
                {"code": "NO_AUDIT_PLAN", "message": "项目尚未配置审核计划"}
            )
        if unsubmitted_records:
            blockers.append(
                {
                    "code": "UNSUBMITTED_RECORDS",
                    "message": f"有 {len(unsubmitted_records)} 份区域记录尚未提交",
                }
            )
        if empty_submitted_records:
            blockers.append(
                {
                    "code": "EMPTY_SUBMITTED_RECORDS",
                    "message": f"有 {len(empty_submitted_records)} 份已提交记录没有有效检查项",
                }
            )
        if pending_drafts:
            blockers.append(
                {
                    "code": "PENDING_AI_DRAFTS",
                    "message": f"有 {len(pending_drafts)} 条 AI 草稿尚未人工确认",
                }
            )
        if unclosed_ncs:
            blockers.append(
                {
                    "code": "UNCLOSED_NONCONFORMITIES",
                    "message": f"有 {len(unclosed_ncs)} 条不符合项尚未验证或关闭",
                    "statuses": sorted(
                        {str(item.get("status") or "") for item in unclosed_ncs}
                    ),
                }
            )
        if incomplete_plans:
            blockers.append(
                {
                    "code": "INCOMPLETE_PLAN_ITEMS",
                    "message": f"有 {len(incomplete_plans)} 个审核计划项尚未完成",
                }
            )
        if uncovered_clauses:
            blockers.append(
                {
                    "code": "PLAN_CLAUSE_GAPS",
                    "message": f"计划条款覆盖率为 {clause_coverage}%，仍有 {len(uncovered_clauses)} 项未覆盖",
                    "clauses": uncovered_clauses,
                }
            )
        if not active_documents:
            blockers.append(
                {"code": "NO_PROJECT_DOCUMENTS", "message": "项目尚未上传可用的专属资料"}
            )
        if failed_documents:
            blockers.append(
                {
                    "code": "FAILED_DOCUMENTS",
                    "message": f"有 {len(failed_documents)} 份资料解析失败",
                }
            )
        if not opening_meetings:
            blockers.append(
                {"code": "NO_OPENING_MEETING", "message": "尚未形成首次会议记录"}
            )
        if not closing_meetings:
            blockers.append(
                {"code": "NO_CLOSING_MEETING", "message": "尚未形成末次会议记录"}
            )
        if (opening_meetings and closing_meetings) and not meeting_sign_in:
            blockers.append(
                {"code": "NO_MEETING_SIGN_IN", "message": "首次/末次会议缺少签到记录"}
            )

        if not management_documents:
            warnings.append(
                {"code": "NO_MANAGEMENT_DOCUMENTS", "message": "案卷中未识别到管理手册或程序文件"}
            )
        if not reports:
            warnings.append(
                {"code": "NO_AUDIT_REPORT", "message": "审核报告尚未生成，最终案卷暂未就绪"}
            )
        if quarantined_documents:
            warnings.append(
                {
                    "code": "QUARANTINED_DOCUMENTS",
                    "message": f"有 {len(quarantined_documents)} 份高风险资料已隔离，不参与检索和交付",
                }
            )
        if archive_only_documents:
            warnings.append(
                {
                    "code": "ARCHIVE_ONLY_DOCUMENTS",
                    "message": f"有 {len(archive_only_documents)} 份旧格式资料仅归档、不可检索",
                }
            )

        checks = {
            "organization_materials": archive_checks["A_organization_materials"],
            "audit_plan": archive_checks["B_audit_plan"],
            "area_records": archive_checks["E_area_records"],
            "meetings": archive_checks[
                "D_opening_closing_meetings_and_sign_in"
            ],
            "ai_drafts": not pending_drafts,
            "nonconformities": archive_checks["G_nonconformity_closure"],
            "document_index": not failed_documents,
            "audit_report": archive_checks["F_audit_report"],
            "document_manifest": archive_checks["I_document_manifest"],
        }
        consistency = {
            "passed": not blockers,
            "plan_count": len(plan_items),
            "record_count": len(records),
            "confirmed_draft_count": len(
                [item for item in drafts if item.get("status") == "confirmed"]
            ),
            "nonconformity_count": len(ncs),
            "unclosed_nonconformity_count": len(unclosed_ncs),
            "planned_clause_count": len(planned_clauses),
            "covered_clause_count": len(covered_clauses),
            "clause_coverage": clause_coverage,
            "uncovered_clauses": uncovered_clauses,
            "invalid_submitted_record_count": len(empty_submitted_records),
        }
        checked_at = datetime.now(timezone.utc).isoformat()
        return {
            "passed": not blockers,
            "score": archive_completeness_score,
            "completeness_score": archive_completeness_score,
            "consistency_score": 100 if not blockers else max(0, 100 - len(blockers) * 20),
            "blocking_count": len(blockers),
            "warning_count": len(warnings),
            "blockers": blockers,
            "warnings": warnings,
            "issues": [{**item, "level": "blocking"} for item in blockers] + [{**item, "level": "warning"} for item in warnings],
            "completeness": checks,
            "consistency": consistency,
            "archive_checks": archive_checks,
            "archive_completeness_score": archive_completeness_score,
            "archive_ready": archive_ready,
            "source_snapshot": snapshot,
            "checked_at": checked_at,
        }

    @staticmethod
    def _active_documents_statement(project_id: UUID):
        return select(ProjectDocument).where(
            ProjectDocument.project_id == project_id,
            ProjectDocument.is_deleted.is_(False),
        )

    @staticmethod
    def _iso_value(value: Any) -> str | None:
        if value is None:
            return None
        isoformat = getattr(value, "isoformat", None)
        return isoformat() if callable(isoformat) else str(value)

    @staticmethod
    def _member_display_name(member: Any) -> str:
        if member is None:
            return "未命名审核员"
        for attribute in ("full_name", "real_name", "name", "username"):
            value = getattr(member, attribute, None)
            if value:
                return str(value)
        return str(getattr(member, "id", "未命名审核员"))

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

    @classmethod
    def _is_valid_record_item(cls, item: dict[str, Any]) -> bool:
        evaluation = str(item.get("evaluation") or "").strip()
        has_subject = cls._has_content(item.get("title")) or cls._has_content(
            item.get("clause_no")
        )
        has_record = cls._has_content(item.get("evidence")) or cls._has_content(
            item.get("findings")
        )
        return evaluation in {"1", "2", "3"} and has_subject and has_record

    @staticmethod
    def _is_nc_closed(item: dict[str, Any]) -> bool:
        return str(item.get("status") or "").strip().lower() in {
            "verified",
            "closed",
        }

    @classmethod
    def _clause_tokens(cls, value: Any) -> set[str]:
        if isinstance(value, dict):
            return {
                token for child in value.values() for token in cls._clause_tokens(child)
            }
        if isinstance(value, (list, tuple, set)):
            return {
                token for child in value for token in cls._clause_tokens(child)
            }
        if value is None:
            return set()
        return set(re.findall(r"(?<!\d)\d+(?:\.\d+)*(?!\d)", str(value)))

    @classmethod
    def _has_content(cls, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, dict):
            return any(cls._has_content(item) for item in value.values())
        if isinstance(value, (list, tuple, set)):
            return any(cls._has_content(item) for item in value)
        return bool(str(value).strip())

    async def generate(
        self,
        db: AsyncSession,
        project_id: UUID,
        artifact_types: list[str],
        created_by: UUID,
        area_record_id: UUID | None = None,
    ) -> list[ProjectArtifact]:
        project = await db.get(AuditProject, project_id)
        if not project:
            raise ValueError("审核项目不存在")
        snapshot = await self.source_snapshot(db, project_id)
        quality = await self.quality_check(db, project_id)
        generated: list[ProjectArtifact] = []
        for artifact_type in artifact_types:
            if artifact_type == "area_record":
                records = (
                    await db.execute(
                        select(AuditAreaRecord)
                        .where(AuditAreaRecord.project_id == project_id)
                        .options(
                            selectinload(AuditAreaRecord.items),
                            selectinload(AuditAreaRecord.area),
                            selectinload(AuditAreaRecord.plan_item),
                        )
                    )
                ).scalars().all()
                if area_record_id:
                    records = [item for item in records if item.id == area_record_id]
                for record in records:
                    content = await run_in_threadpool(self._area_record_docx, project, record)
                    generated.append(await self._store(db, project, "area_record", f"区域审核记录_{self._area_name(record)}_{record.id}.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", snapshot, created_by))
            elif artifact_type == "meeting_record":
                for meeting in snapshot.get("meetings") or []:
                    meeting_type = self._meeting_type_label(meeting.get("type"))
                    generated.append(
                        await self._store(
                            db,
                            project,
                            "meeting_record",
                            f"{meeting_type}_{meeting.get('id')}.docx",
                            await run_in_threadpool(self._meeting_docx, project, meeting),
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            snapshot,
                            created_by,
                        )
                    )
            elif artifact_type == "audit_report":
                await self._create_report_version(
                    db, project, snapshot, quality, created_by
                )
                buffer = await generate_audit_report_word(db, project_id)
                generated.append(await self._store(db, project, "audit_report", f"审核报告_{project.project_no}.docx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", snapshot, created_by))
            elif artifact_type == "nc_summary":
                ncs = (await db.execute(select(Nonconformity).where(Nonconformity.project_id == project_id))).scalars().all()
                generated.append(await self._store(db, project, "nc_summary", f"不符合项汇总_{project.project_no}.docx", await run_in_threadpool(self._nc_summary_docx, project, ncs), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", snapshot, created_by))
            elif artifact_type == "manifest":
                # 面向交付用户：完整性检查用 Word，不再输出 JSON
                content = await run_in_threadpool(self._quality_check_docx, project, quality, snapshot)
                generated.append(
                    await self._store(
                        db,
                        project,
                        "manifest",
                        f"资料完整性检查_{project.project_no}.docx",
                        content,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        snapshot,
                        created_by,
                    )
                )
        await self._update_report_snapshot(db, project_id, snapshot, quality)
        await db.commit()
        return generated

    async def generate_package(self, db: AsyncSession, project_id: UUID, created_by: UUID) -> ProjectArtifact:
        project = await db.get(AuditProject, project_id)
        if not project:
            raise ValueError("审核项目不存在")
        await self.generate(
            db,
            project_id,
            [
                "area_record",
                "meeting_record",
                "audit_report",
                "nc_summary",
                "manifest",
            ],
            created_by,
        )
        snapshot = await self.source_snapshot(db, project_id)
        quality = await self.quality_check(db, project_id)
        documents = (
            await db.execute(self._active_documents_statement(project_id))
        ).scalars().all()
        artifacts = (
            await db.execute(
                select(ProjectArtifact).where(
                    ProjectArtifact.project_id == project_id,
                    ProjectArtifact.artifact_type != "package",
                    ProjectArtifact.status == "ready",
                    ProjectArtifact.is_deleted.is_(False),
                )
            )
        ).scalars().all()
        buffer = io.BytesIO()
        manifest_files: list[dict[str, Any]] = []
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            def add_bytes(archive_path: str, content: bytes) -> None:
                archive.writestr(archive_path, content)
                manifest_files.append({
                    "path": archive_path,
                    "size": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                })

            # 用户可读交付物统一为 Word（不再向用户暴露业务 JSON）
            add_bytes(
                "A组织信息/项目摘要.docx",
                await run_in_threadpool(self._project_summary_docx, project, snapshot),
            )
            add_bytes(
                "B审核通知/审核计划汇总.docx",
                await run_in_threadpool(self._audit_plan_docx, project, snapshot),
            )
            add_bytes(
                "I案卷检查表/资料完整性检查.docx",
                await run_in_threadpool(self._quality_check_docx, project, quality, snapshot),
            )
            for document in documents:
                if self._is_quarantined_metadata(document.document_metadata):
                    continue
                path = resolve_storage_path(document.stored_path)
                if path:
                    folder = self._document_archive_folder(document)
                    add_bytes(f"{folder}/{_safe_name(document.original_filename)}", path.read_bytes())
            folder_map = {
                "area_record": "E审核记录汇总（含附件）/审核记录",
                "meeting_record": "E审核记录汇总（含附件）/会议记录",
                "audit_report": "F审核计划和审核报告",
                "nc_summary": "G不符合项整改汇总",
                "manifest": "I案卷检查表",
            }
            for artifact in self._latest_artifacts(artifacts):
                path = resolve_storage_path(artifact.path)
                if not path:
                    continue
                # 避免与上方固定路径的完整性 Word 重复塞两份
                if artifact.artifact_type == "manifest":
                    continue
                add_bytes(
                    f"{folder_map.get(artifact.artifact_type, 'Z其它文件')}/{_safe_name(artifact.filename)}",
                    path.read_bytes(),
                )
            for archive_path, photo_path in self._record_photo_files(snapshot):
                add_bytes(archive_path, photo_path.read_bytes())
            # 文件清单也用 Word，便于客户核对
            add_bytes(
                "I案卷检查表/资料包文件清单.docx",
                await run_in_threadpool(self._package_file_list_docx, project, quality, manifest_files),
            )
        return await self._store(db, project, "package", f"完整审核资料包_{project.project_no}.zip", buffer.getvalue(), "application/zip", snapshot, created_by)

    async def _store(self, db: AsyncSession, project: AuditProject, artifact_type: str, filename: str, content: bytes, mime_type: str, snapshot: dict[str, Any], created_by: UUID) -> ProjectArtifact:
        result = await db.execute(select(func.max(ProjectArtifact.version)).where(ProjectArtifact.project_id == project.id, ProjectArtifact.artifact_type == artifact_type))
        version = (result.scalar_one_or_none() or 0) + 1
        directory = Path(settings.UPLOAD_DIR) / "audit_projects" / str(project.id) / "artifacts"
        directory.mkdir(parents=True, exist_ok=True)
        versioned_name = f"v{version}_{_safe_name(filename)}"
        path = directory / versioned_name
        path.write_bytes(content)
        artifact = ProjectArtifact(project_id=project.id, artifact_type=artifact_type, path=storage_key(path), filename=filename, mime_type=mime_type, file_size=len(content), checksum_sha256=hashlib.sha256(content).hexdigest(), version=version, source_snapshot=snapshot, status="ready", progress=100, created_by=created_by)
        db.add(artifact)
        await db.flush()
        return artifact

    @staticmethod
    async def _create_report_version(
        db: AsyncSession,
        project: AuditProject,
        snapshot: dict[str, Any],
        quality: dict[str, Any],
        created_by: UUID,
    ) -> AuditReport:
        result = await db.execute(
            select(func.max(AuditReport.version)).where(
                AuditReport.project_id == project.id
            )
        )
        version = (result.scalar_one_or_none() or 0) + 1
        record_items = [
            item
            for record in snapshot["area_records"]
            for item in record.get("items", [])
        ]
        nonconformities = snapshot["nonconformities"]
        report = AuditReport(
            project_id=project.id,
            report_type=(
                "EnMS"
                if (project.certification_systems or []) == ["En"]
                else "combined"
            ),
            report_no=f"REP-{str(project.project_no)[:32]}-V{version}",
            audit_summary={
                "project_no": project.project_no,
                "audit_type": project.audit_type,
                "certification_systems": project.certification_systems or [],
                "audit_scope": project.audit_scope or {},
                "audit_criteria": project.audit_criteria or [],
            },
            findings_summary={
                "total_items": len(record_items),
                "compliant": len(
                    [item for item in record_items if str(item.get("evaluation")) == "1"]
                ),
                "partial": len(
                    [item for item in record_items if str(item.get("evaluation")) == "2"]
                ),
                "nonconforming": len(
                    [item for item in record_items if str(item.get("evaluation")) == "3"]
                ),
                "nonconformities": len(nonconformities),
            },
            nonconformity_ids=[UUID(item["id"]) for item in nonconformities],
            conclusion=(
                "conditional"
                if any(
                    not ProjectArtifactService._is_nc_closed(item)
                    for item in nonconformities
                )
                else "recommend"
            ),
            conclusion_notes="报告由正式审核记录快照生成，发布前完整性与一致性检查已通过。",
            prepared_by=created_by,
            prepared_at=datetime.now(timezone.utc),
            source_snapshot=snapshot,
            completeness_check={
                "score": quality["completeness_score"],
                "checks": quality["completeness"],
                "blockers": quality["blockers"],
                "warnings": quality["warnings"],
                "archive_checks": quality["archive_checks"],
                "archive_completeness_score": quality[
                    "archive_completeness_score"
                ],
                "archive_ready": quality["archive_ready"],
                "checked_at": quality["checked_at"],
            },
            consistency_check={
                "score": quality["consistency_score"],
                **quality["consistency"],
                "checked_at": quality["checked_at"],
            },
            version=version,
        )
        db.add(report)
        await db.flush()
        return report

    @staticmethod
    def _latest_artifacts(
        artifacts: list[ProjectArtifact],
    ) -> list[ProjectArtifact]:
        """Keep the latest version of each distinct deliverable file.

        Area records share artifact_type but different filenames; keying only by
        type would drop all but one region record from the ZIP package.
        """
        latest: dict[tuple[str, str], ProjectArtifact] = {}
        for artifact in artifacts:
            key = (str(artifact.artifact_type or ""), str(artifact.filename or artifact.id))
            current = latest.get(key)
            if current is None or int(artifact.version or 0) > int(current.version or 0):
                latest[key] = artifact
        return list(latest.values())

    @staticmethod
    def _area_name(record: AuditAreaRecord) -> str:
        """Resolve the formal area relation while retaining legacy record support."""
        direct_name = getattr(record, "area_name", None)
        if direct_name:
            return str(direct_name)
        area = getattr(record, "area", None)
        if area and area.area_name:
            return str(area.area_name)
        plan_item = getattr(record, "plan_item", None)
        if plan_item and plan_item.area_name:
            return str(plan_item.area_name)
        return "未命名区域"

    @staticmethod
    def _docx_bytes(document: Document) -> bytes:
        buffer = io.BytesIO()
        document.save(buffer)
        return buffer.getvalue()

    @staticmethod
    def _status_label(status: str | None) -> str:
        return {
            "pending": "待开始",
            "in_progress": "进行中",
            "completed": "已完成",
            "submitted": "已提交",
            "reviewed": "已复核",
            "draft": "草稿",
            "open": "已开立",
            "corrected": "已整改",
            "pending_verification": "待验证",
            "verified": "已验证",
            "closed": "已关闭",
            "cancelled": "已取消",
        }.get(str(status or ""), str(status or "—"))

    @staticmethod
    def _eval_label(value: Any) -> str:
        return {"1": "符合", "2": "基本符合", "3": "不符合"}.get(str(value or ""), str(value or "—"))

    @staticmethod
    def _meeting_type_label(value: Any) -> str:
        return {
            "opening": "首次会议记录",
            "opening_meeting": "首次会议记录",
            "interim": "阶段沟通记录",
            "internal": "审核组内部沟通记录",
            "closing": "末次会议记录",
            "closing_meeting": "末次会议记录",
        }.get(str(value or "").lower(), "沟通会议记录")

    @classmethod
    def _document_archive_folder(cls, document: ProjectDocument) -> str:
        metadata = document.document_metadata or {}
        category = str(metadata.get("category") or document.document_type or "").lower()
        filename = str(document.original_filename or "")
        archive_section = str(metadata.get("archive_section") or "").upper()
        section_folders = {
            "A": "A组织信息",
            "B": "B审核通知",
            "C": "C管理手册和程序文件",
            "D": "D审核资料汇总",
            "E": "E审核记录汇总（含附件）",
            "F": "F审核计划和审核报告",
            "G": "G不符合项整改汇总",
            "I": "I案卷检查表",
            "Z": "Z其它文件",
        }
        if archive_section in section_folders:
            return section_folders[archive_section]

        if category in {"manual", "procedure"} or any(
            keyword in filename for keyword in ("管理手册", "程序文件")
        ):
            return "C管理手册和程序文件"
        if category == "nonconformity" or any(
            keyword in filename for keyword in ("不符合", "整改", "审定意见")
        ):
            return "G不符合项整改汇总"
        if category == "audit_report" or any(
            keyword in filename
            for keyword in ("审核报告", "再认证报告", "信息确认", "能源绩效表")
        ):
            return "F审核计划和审核报告"
        if category == "audit_plan" or any(
            keyword in filename
            for keyword in ("审核计划", "审核任务书", "审核策划", "审核方案", "审核通知")
        ):
            return "B审核通知"
        if any(
            keyword in filename
            for keyword in ("案卷", "资料审查和传递", "资料包文件清单")
        ):
            return "I案卷检查表"
        if any(
            keyword in filename
            for keyword in ("签到", "承诺", "顾客满意", "文件审核", "劳务费", "见证报告", "验证报告")
        ):
            return "D审核资料汇总"
        if category == "organization" or any(
            keyword in filename
            for keyword in (
                "申请书",
                "合同",
                "组织架构",
                "营业执照",
                "资质",
                "许可证",
                "平面布置",
                "工艺流程",
                "风险清单",
                "环境因素",
                "能源评审",
                "职业危害",
                "产品执行标准",
                "上一周期",
                "信息传递单",
            )
        ):
            return "A组织信息"
        if category in {"meeting", "record"} or any(
            keyword in filename
            for keyword in ("现场审核记录", "沟通记录", "沟通会议", "证书及标志检查")
        ):
            return "E审核记录汇总（含附件）"
        if "证书" in filename:
            return "Z其它文件"
        return "Z其它文件"

    @classmethod
    def _record_photo_files(
        cls, snapshot: dict[str, Any]
    ) -> list[tuple[str, Path]]:
        files: list[tuple[str, Path]] = []
        for record_index, record in enumerate(
            snapshot.get("area_records") or [], start=1
        ):
            area = _safe_name(str(record.get("area") or f"区域{record_index}"))
            for item_index, item in enumerate(record.get("items") or [], start=1):
                item_id = _safe_name(str(item.get("id") or item_index))
                for photo_index, reference in enumerate(
                    item.get("photos") or [], start=1
                ):
                    path = cls._resolve_upload_path(reference)
                    if not path:
                        continue
                    archive_path = (
                        "E审核记录汇总（含附件）/附件/"
                        f"{area}/{item_id}_{photo_index}_{_safe_name(path.name)}"
                    )
                    files.append((archive_path, path))
        return files

    @staticmethod
    def _resolve_upload_path(reference: Any) -> Path | None:
        return resolve_storage_path(reference)

    @staticmethod
    def _meeting_docx(project: AuditProject, meeting: dict[str, Any]) -> bytes:
        document = Document()
        meeting_label = ProjectArtifactService._meeting_type_label(
            meeting.get("type")
        )
        document.add_heading(meeting_label, 0)
        info = document.add_table(rows=1, cols=2)
        info.style = "Table Grid"
        info.rows[0].cells[0].text = "项目"
        info.rows[0].cells[1].text = "内容"
        rows = (
            ("项目", f"{project.title}（{project.project_no}）"),
            ("会议时间", meeting.get("time") or "—"),
            (
                "审核组参会人员",
                "、".join(meeting.get("audit_team_members") or []) or "—",
            ),
            ("企业参会人员", meeting.get("participants_enterprise") or "—"),
        )
        for label, value in rows:
            cells = info.add_row().cells
            cells[0].text = str(label)
            cells[1].text = str(value)
        document.add_heading("会议要点", level=1)
        document.add_paragraph(meeting.get("key_points") or "尚未填写")
        document.add_heading("会议纪要", level=1)
        document.add_paragraph(meeting.get("minutes") or "尚未填写")
        document.add_heading("签到记录", level=1)
        sign_in = meeting.get("sign_in_sheet")
        if not ProjectArtifactService._has_content(sign_in):
            document.add_paragraph("尚未上传签到记录")
        elif isinstance(sign_in, dict):
            table = document.add_table(rows=1, cols=2)
            table.style = "Table Grid"
            table.rows[0].cells[0].text = "项目"
            table.rows[0].cells[1].text = "内容"
            for key, value in sign_in.items():
                cells = table.add_row().cells
                cells[0].text = str(key)
                cells[1].text = (
                    json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (dict, list))
                    else str(value)
                )
        else:
            document.add_paragraph(
                json.dumps(sign_in, ensure_ascii=False)
                if isinstance(sign_in, list)
                else str(sign_in)
            )
        return ProjectArtifactService._docx_bytes(document)

    @staticmethod
    def _project_summary_docx(project: AuditProject, snapshot: dict[str, Any]) -> bytes:
        document = Document()
        document.add_heading("审核项目摘要", 0)
        info = snapshot.get("project") or {}
        systems = "、".join(info.get("certification_systems") or project.certification_systems or []) or "—"
        rows = [
            ("项目名称", project.title or info.get("title") or "—"),
            ("项目编号", project.project_no or info.get("project_no") or "—"),
            ("项目状态", ProjectArtifactService._status_label(project.status or info.get("status"))),
            ("审核类型", project.audit_type or info.get("audit_type") or "—"),
            ("认证体系", systems),
            ("计划项数量", str(len(snapshot.get("plan_items") or []))),
            ("区域记录数量", str(len(snapshot.get("area_records") or []))),
            ("会议记录数量", str(len(snapshot.get("meetings") or []))),
            ("审核报告数量", str(len(snapshot.get("reports") or []))),
            ("不符合项数量", str(len(snapshot.get("nonconformities") or []))),
            ("项目资料数量", str(len(snapshot.get("documents") or []))),
            ("生成时间", datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")),
        ]
        table = document.add_table(rows=1, cols=2)
        table.style = "Table Grid"
        table.rows[0].cells[0].text = "项目"
        table.rows[0].cells[1].text = "内容"
        for label, value in rows:
            cells = table.add_row().cells
            cells[0].text = label
            cells[1].text = str(value)
        document.add_paragraph("")
        document.add_paragraph("说明：本文件为完整审核资料包中的项目概览，供客户与审核组查阅。")
        return ProjectArtifactService._docx_bytes(document)

    @staticmethod
    def _audit_plan_docx(project: AuditProject, snapshot: dict[str, Any]) -> bytes:
        document = Document()
        document.add_heading("审核计划汇总", 0)
        document.add_paragraph(f"项目：{project.title or ''}（{project.project_no or ''}）")
        plan_items = snapshot.get("plan_items") or []
        if not plan_items:
            document.add_paragraph("尚未配置审核计划项。")
        else:
            table = document.add_table(rows=1, cols=8)
            table.style = "Table Grid"
            for cell, title in zip(
                table.rows[0].cells,
                (
                    "日期",
                    "时间",
                    "组",
                    "审核员",
                    "区域/计划项",
                    "体系",
                    "状态",
                    "条款摘要",
                ),
            ):
                cell.text = title
            for item in plan_items:
                clauses = item.get("clauses") or []
                clause_text = "、".join(str(c) for c in clauses[:12])
                if len(clauses) > 12:
                    clause_text += f" 等共 {len(clauses)} 项"
                cells = table.add_row().cells
                values = (
                    item.get("date") or "—",
                    "-".join(
                        str(value)
                        for value in (item.get("time_start"), item.get("time_end"))
                        if value
                    )
                    or "—",
                    item.get("group") or "—",
                    "、".join(
                        str(auditor.get("name") or auditor.get("id"))
                        for auditor in (item.get("assigned_auditors") or [])
                    )
                    or "—",
                    item.get("area") or "—",
                    "、".join(item.get("certification_systems") or []) or "—",
                    ProjectArtifactService._status_label(item.get("status")),
                    clause_text or "—",
                )
                for cell, value in zip(cells, values):
                    cell.text = str(value)
        return ProjectArtifactService._docx_bytes(document)

    @staticmethod
    def _quality_check_docx(
        project: AuditProject,
        quality: dict[str, Any],
        snapshot: dict[str, Any],
    ) -> bytes:
        document = Document()
        document.add_heading("资料完整性检查报告", 0)
        document.add_paragraph(f"项目：{project.title or ''}（{project.project_no or ''}）")
        document.add_paragraph(
            f"检查时间：{quality.get('checked_at') or datetime.now(timezone.utc).isoformat()}"
        )
        document.add_paragraph(
            f"检查结果：{'通过' if quality.get('passed') else '未通过'}  "
            f"完整度 {quality.get('completeness_score', quality.get('score', '—'))}%  "
            f"一致度 {quality.get('consistency_score', '—')}%"
        )

        document.add_heading("检查项", level=1)
        checks = quality.get("completeness") or {}
        check_labels = {
            "organization_materials": "组织资料已上传",
            "audit_plan": "审核计划已配置",
            "area_records": "区域记录已提交",
            "meetings": "首次/末次会议及签到齐全",
            "ai_drafts": "AI 草稿已确认",
            "nonconformities": "不符合项已验证或关闭",
            "document_index": "资料解析正常",
            "audit_report": "审核报告已形成",
            "document_manifest": "文件清单可生成",
        }
        table = document.add_table(rows=1, cols=2)
        table.style = "Table Grid"
        table.rows[0].cells[0].text = "检查项"
        table.rows[0].cells[1].text = "结果"
        for key, label in check_labels.items():
            cells = table.add_row().cells
            cells[0].text = label
            cells[1].text = "通过" if checks.get(key) else "未通过"

        document.add_heading("A-I 案卷完成度", level=1)
        document.add_paragraph(
            f"案卷状态：{'就绪' if quality.get('archive_ready') else '未就绪'}  "
            f"完成度：{quality.get('archive_completeness_score', '—')}%"
        )
        archive_labels = {
            "A_organization_materials": "A 组织资料",
            "B_audit_plan": "B 审核计划",
            "C_management_documents": "C 管理手册和程序文件",
            "D_opening_closing_meetings_and_sign_in": "D 首次/末次会议及签到",
            "E_area_records": "E 现场审核记录",
            "F_audit_report": "F 审核报告",
            "G_nonconformity_closure": "G 不符合项闭环",
            "I_document_manifest": "I 案卷文件清单",
        }
        archive_table = document.add_table(rows=1, cols=2)
        archive_table.style = "Table Grid"
        archive_table.rows[0].cells[0].text = "案卷项"
        archive_table.rows[0].cells[1].text = "结果"
        archive_checks = quality.get("archive_checks") or {}
        for key, label in archive_labels.items():
            cells = archive_table.add_row().cells
            cells[0].text = label
            cells[1].text = "齐全" if archive_checks.get(key) else "缺失"

        blockers = quality.get("blockers") or []
        document.add_heading("阻断项", level=1)
        if not blockers:
            document.add_paragraph("无阻断项。")
        else:
            for item in blockers:
                document.add_paragraph(
                    f"• {item.get('message') or item.get('code') or item}",
                    style="List Bullet",
                )

        warnings = quality.get("warnings") or []
        document.add_heading("提示项", level=1)
        if not warnings:
            document.add_paragraph("无提示项。")
        else:
            for item in warnings:
                document.add_paragraph(
                    f"• {item.get('message') or item.get('code') or item}",
                    style="List Bullet",
                )

        consistency = quality.get("consistency") or {}
        document.add_heading("数量统计", level=1)
        stats = [
            ("审核计划项", consistency.get("plan_count", len(snapshot.get("plan_items") or []))),
            ("区域记录", consistency.get("record_count", len(snapshot.get("area_records") or []))),
            ("已确认 AI 记录", consistency.get("confirmed_draft_count", 0)),
            ("不符合项", consistency.get("nonconformity_count", len(snapshot.get("nonconformities") or []))),
            ("未闭环不符合项", consistency.get("unclosed_nonconformity_count", 0)),
            ("计划条款覆盖率", f"{consistency.get('clause_coverage', '—')}%"),
        ]
        stat_table = document.add_table(rows=1, cols=2)
        stat_table.style = "Table Grid"
        stat_table.rows[0].cells[0].text = "指标"
        stat_table.rows[0].cells[1].text = "数量"
        for label, value in stats:
            cells = stat_table.add_row().cells
            cells[0].text = label
            cells[1].text = str(value)
        return ProjectArtifactService._docx_bytes(document)

    @staticmethod
    def _package_file_list_docx(
        project: AuditProject,
        quality: dict[str, Any],
        files: list[dict[str, Any]],
    ) -> bytes:
        document = Document()
        document.add_heading("资料包文件清单", 0)
        document.add_paragraph(f"项目：{project.title or ''}（{project.project_no or ''}）")
        document.add_paragraph(
            f"生成时间：{datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M')}  "
            f"质量门禁：{'通过' if quality.get('passed') else '未通过'}"
        )
        document.add_paragraph(f"文件总数：{len(files)}")
        table = document.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        for cell, title in zip(table.rows[0].cells, ("序号", "路径", "大小(字节)", "SHA-256")):
            cell.text = title
        for index, item in enumerate(files, start=1):
            cells = table.add_row().cells
            values = (
                str(index),
                item.get("path") or "",
                str(item.get("size") or 0),
                item.get("sha256") or "",
            )
            for cell, value in zip(cells, values):
                cell.text = str(value)
        document.add_paragraph("")
        document.add_paragraph("说明：可用本清单核对资料包内文件是否齐全、是否被篡改。")
        return ProjectArtifactService._docx_bytes(document)

    @staticmethod
    def _area_record_docx(project: AuditProject, record: AuditAreaRecord) -> bytes:
        document = Document()
        document.add_heading("区域审核记录", 0)
        for label, value in (
            ("项目", project.title),
            ("项目编号", project.project_no),
            ("区域", ProjectArtifactService._area_name(record)),
            ("审核日期", record.audit_date),
            ("状态", ProjectArtifactService._status_label(record.status)),
        ):
            document.add_paragraph(f"{label}：{value or ''}")
        document.add_heading("审核结论", level=1)
        document.add_paragraph(record.conclusion or "尚未填写")
        document.add_heading("条款与证据记录", level=1)
        if not record.items:
            document.add_paragraph("尚无已确认的审核记录项")
        else:
            table = document.add_table(rows=1, cols=4)
            table.style = "Table Grid"
            for cell, title in zip(
                table.rows[0].cells,
                ("检查表", "审核记录", "标准号/条款号", "评估"),
            ):
                cell.text = title
            for item in record.items:
                cells = table.add_row().cells
                check_text = getattr(item, "item_title", None) or "检查项"
                check_method = getattr(item, "item_check_method", None)
                if check_method:
                    check_text = f"{check_text}\n检查方法：{check_method}"
                audit_parts = []
                if getattr(item, "audit_evidence", None):
                    audit_parts.append(f"审核证据：{item.audit_evidence}")
                if getattr(item, "audit_findings", None):
                    audit_parts.append(f"审核发现：{item.audit_findings}")
                audit_parts.append(
                    "来源：AI辅助，经人工确认"
                    if bool(getattr(item, "ai_generated", False))
                    else "来源：人工记录"
                )
                if getattr(item, "ai_basis", None):
                    audit_parts.append(f"AI依据：{item.ai_basis}")
                clause_parts = [
                    str(value)
                    for value in (
                        getattr(item, "certification_system", None),
                        getattr(item, "clause_no_snapshot", None),
                    )
                    if value
                ]
                evaluation = str(getattr(item, "evaluation_3level", None) or "")
                values = (
                    check_text,
                    "\n".join(audit_parts),
                    " ".join(clause_parts) or "—",
                    (
                        f"{evaluation}（{ProjectArtifactService._eval_label(evaluation)}）"
                        if evaluation
                        else "—"
                    ),
                )
                for cell, value in zip(cells, values):
                    cell.text = str(value)
        return ProjectArtifactService._docx_bytes(document)

    @staticmethod
    def _nc_summary_docx(project: AuditProject, ncs: list[Nonconformity]) -> bytes:
        document = Document()
        document.add_heading("不符合项汇总", 0)
        document.add_paragraph(f"项目：{project.title}（{project.project_no}）")
        if not ncs:
            document.add_paragraph("本项目暂无不符合项。")
            return ProjectArtifactService._docx_bytes(document)
        table = document.add_table(rows=1, cols=6)
        table.style = "Table Grid"
        for cell, title in zip(
            table.rows[0].cells,
            ("编号", "条款", "严重度", "描述", "状态", "整改要求"),
        ):
            cell.text = title
        for nc in ncs:
            cells = table.add_row().cells
            values = (
                nc.nc_no or "",
                nc.clause_no or "",
                nc.severity or "",
                nc.description or "",
                ProjectArtifactService._status_label(nc.status),
                nc.corrective_action_required or "",
            )
            for cell, value in zip(cells, values):
                cell.text = str(value)
        return ProjectArtifactService._docx_bytes(document)

    @staticmethod
    async def _update_report_snapshot(
        db: AsyncSession,
        project_id: UUID,
        snapshot: dict[str, Any],
        quality: dict[str, Any],
    ) -> None:
        report = (await db.execute(select(AuditReport).where(AuditReport.project_id == project_id).order_by(AuditReport.version.desc()))).scalars().first()
        if report:
            report.source_snapshot = snapshot
            report.completeness_check = {
                "score": quality["completeness_score"],
                "checks": quality["completeness"],
                "blockers": quality["blockers"],
                "warnings": quality["warnings"],
                "archive_checks": quality["archive_checks"],
                "archive_completeness_score": quality[
                    "archive_completeness_score"
                ],
                "archive_ready": quality["archive_ready"],
                "checked_at": quality["checked_at"],
            }
            report.consistency_check = {
                "score": quality["consistency_score"],
                **quality["consistency"],
                "checked_at": quality["checked_at"],
            }


project_artifact_service = ProjectArtifactService()
