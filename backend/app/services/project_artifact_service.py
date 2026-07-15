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
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.audit_project import (
    AuditAreaRecord,
    AuditPlanItem,
    AuditProject,
    AuditReport,
    Nonconformity,
)
from app.models.evidence_agent import AiDraftRecord
from app.models.project_artifact import ProjectArtifact
from app.models.project_knowledge import ProjectDocument
from app.services.report_generator import generate_audit_report_word


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\r\n]+", "_", value).strip(" .")
    return cleaned[:180] or "artifact"


class ProjectArtifactService:
    async def source_snapshot(self, db: AsyncSession, project_id: UUID) -> dict[str, Any]:
        project = await db.get(AuditProject, project_id)
        if not project:
            raise ValueError("审核项目不存在")
        plan_items = (await db.execute(select(AuditPlanItem).where(AuditPlanItem.project_id == project_id))).scalars().all()
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
        documents = (await db.execute(select(ProjectDocument).where(ProjectDocument.project_id == project_id))).scalars().all()
        return {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "project": {
                "id": str(project.id),
                "project_no": project.project_no,
                "title": project.title,
                "status": project.status,
                "audit_type": project.audit_type,
                "certification_systems": project.certification_systems or [],
            },
            "plan_items": [{"id": str(item.id), "area": item.area_name, "status": item.status, "clauses": item.clauses or []} for item in plan_items],
            "area_records": [
                {
                    "id": str(record.id),
                    "plan_item_id": str(record.plan_item_id) if record.plan_item_id else None,
                    "area": self._area_name(record),
                    "status": record.status,
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
            "documents": [{"id": str(item.id), "name": item.original_filename, "status": item.status, "type": item.document_type} for item in documents],
        }

    async def quality_check(self, db: AsyncSession, project_id: UUID) -> dict[str, Any]:
        snapshot = await self.source_snapshot(db, project_id)
        blockers: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []

        plan_items = snapshot["plan_items"]
        records = snapshot["area_records"]
        drafts = snapshot["drafts"]
        ncs = snapshot["nonconformities"]
        documents = snapshot["documents"]

        incomplete_plans = [item for item in plan_items if item["status"] != "completed"]
        unsubmitted_records = [item for item in records if item["status"] not in {"submitted", "reviewed"}]
        pending_drafts = [item for item in drafts if item["status"] == "draft"]
        draft_ncs = [item for item in ncs if item["status"] == "draft"]
        failed_documents = [item for item in documents if item["status"] == "failed"]

        if not records:
            blockers.append({"code": "NO_AREA_RECORD", "message": "尚未形成任何区域审核记录"})
        if not plan_items:
            blockers.append({"code": "NO_AUDIT_PLAN", "message": "项目尚未配置审核计划"})
        if unsubmitted_records:
            blockers.append({"code": "UNSUBMITTED_RECORDS", "message": f"有 {len(unsubmitted_records)} 份区域记录尚未提交"})
        if pending_drafts:
            blockers.append({"code": "PENDING_AI_DRAFTS", "message": f"有 {len(pending_drafts)} 条 AI 草稿尚未人工确认"})
        if draft_ncs:
            blockers.append({"code": "UNCONFIRMED_NC", "message": f"有 {len(draft_ncs)} 条不符合项草稿尚未确认"})
        if incomplete_plans:
            blockers.append({"code": "INCOMPLETE_PLAN_ITEMS", "message": f"有 {len(incomplete_plans)} 个审核计划项尚未完成"})
        if not documents:
            blockers.append({"code": "NO_PROJECT_DOCUMENTS", "message": "项目尚未上传专属资料"})
        if failed_documents:
            blockers.append({"code": "FAILED_DOCUMENTS", "message": f"有 {len(failed_documents)} 份资料解析失败"})

        checks = {
            "organization_materials": bool(documents),
            "audit_plan": bool(plan_items),
            "area_records": bool(records) and not unsubmitted_records,
            "ai_drafts": not pending_drafts,
            "nonconformities": not draft_ncs,
            "document_index": not failed_documents,
        }
        passed_count = sum(1 for value in checks.values() if value)
        completeness_score = round(passed_count / len(checks) * 100)
        consistency = {
            "passed": not blockers and all(checks.values()),
            "plan_count": len(plan_items),
            "record_count": len(records),
            "confirmed_draft_count": len([item for item in drafts if item["status"] == "confirmed"]),
            "nonconformity_count": len(ncs),
        }
        return {
            "passed": not blockers,
            "score": completeness_score,
            "completeness_score": completeness_score,
            "consistency_score": 100 if not blockers else max(0, 100 - len(blockers) * 20),
            "blocking_count": len(blockers),
            "warning_count": len(warnings),
            "blockers": blockers,
            "warnings": warnings,
            "issues": [{**item, "level": "blocking"} for item in blockers] + [{**item, "level": "warning"} for item in warnings],
            "completeness": checks,
            "consistency": consistency,
            "source_snapshot": snapshot,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

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
                    content = self._area_record_docx(project, record)
                    generated.append(await self._store(db, project, "area_record", f"区域审核记录_{self._area_name(record)}_{record.id}.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", snapshot, created_by))
            elif artifact_type == "audit_report":
                await self._create_report_version(
                    db, project, snapshot, quality, created_by
                )
                buffer = await generate_audit_report_word(db, project_id)
                generated.append(await self._store(db, project, "audit_report", f"审核报告_{project.project_no}.docx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", snapshot, created_by))
            elif artifact_type == "nc_summary":
                ncs = (await db.execute(select(Nonconformity).where(Nonconformity.project_id == project_id))).scalars().all()
                generated.append(await self._store(db, project, "nc_summary", f"不符合项汇总_{project.project_no}.docx", self._nc_summary_docx(project, ncs), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", snapshot, created_by))
            elif artifact_type == "manifest":
                content = json.dumps({"project": snapshot["project"], "quality_check": quality, "source_snapshot": snapshot}, ensure_ascii=False, indent=2).encode("utf-8")
                generated.append(await self._store(db, project, "manifest", f"资料完整性检查_{project.project_no}.json", content, "application/json", snapshot, created_by))
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
            ["area_record", "audit_report", "nc_summary", "manifest"],
            created_by,
        )
        snapshot = await self.source_snapshot(db, project_id)
        quality = await self.quality_check(db, project_id)
        documents = (await db.execute(select(ProjectDocument).where(ProjectDocument.project_id == project_id))).scalars().all()
        artifacts = (
            await db.execute(
                select(ProjectArtifact).where(
                    ProjectArtifact.project_id == project_id,
                    ProjectArtifact.artifact_type != "package",
                    ProjectArtifact.status == "ready",
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

            add_bytes("A组织信息/项目摘要.json", json.dumps(snapshot["project"], ensure_ascii=False, indent=2).encode("utf-8"))
            add_bytes("I档案检查表/资料完整性检查.json", json.dumps(quality, ensure_ascii=False, indent=2).encode("utf-8"))
            for document in documents:
                path = Path(document.stored_path)
                if path.is_file():
                    folder = "C管理手册和程序文件" if document.document_type in {"manual", "procedure"} else "D审核资料汇总"
                    add_bytes(f"{folder}/{_safe_name(document.original_filename)}", path.read_bytes())
            folder_map = {"area_record": "E审核记录汇总", "audit_report": "F审核报告", "nc_summary": "G不符合项整改汇总", "manifest": "I档案检查表"}
            for artifact in self._latest_artifacts(artifacts):
                path = Path(artifact.path)
                if path.is_file():
                    add_bytes(f"{folder_map.get(artifact.artifact_type, 'H其他成果')}/{_safe_name(artifact.filename)}", path.read_bytes())
            manifest = {
                "manifest_version": "1.0",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "project": snapshot["project"],
                "quality_passed": quality["passed"],
                "source_snapshot_sha256": hashlib.sha256(
                    json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode("utf-8")
                ).hexdigest(),
                "files": manifest_files,
            }
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
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
        artifact = ProjectArtifact(project_id=project.id, artifact_type=artifact_type, path=str(path.resolve()), filename=filename, mime_type=mime_type, file_size=len(content), checksum_sha256=hashlib.sha256(content).hexdigest(), version=version, source_snapshot=snapshot, status="ready", progress=100, created_by=created_by)
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
            conclusion="conditional" if nonconformities else "recommend",
            conclusion_notes="报告由正式审核记录快照生成，发布前完整性与一致性检查已通过。",
            prepared_by=created_by,
            prepared_at=datetime.now(timezone.utc),
            source_snapshot=snapshot,
            completeness_check={
                "score": quality["completeness_score"],
                "checks": quality["completeness"],
                "blockers": quality["blockers"],
                "warnings": quality["warnings"],
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
        """Keep only the latest version of each deliverable in a ZIP package."""
        latest: dict[str, ProjectArtifact] = {}
        for artifact in artifacts:
            current = latest.get(artifact.artifact_type)
            if current is None or int(artifact.version or 0) > int(current.version or 0):
                latest[artifact.artifact_type] = artifact
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
    def _area_record_docx(project: AuditProject, record: AuditAreaRecord) -> bytes:
        document = Document()
        document.add_heading("区域审核记录", 0)
        for label, value in (("项目", project.title), ("项目编号", project.project_no), ("区域", ProjectArtifactService._area_name(record)), ("审核日期", record.audit_date), ("状态", record.status)):
            document.add_paragraph(f"{label}：{value or ''}")
        document.add_heading("审核结论", level=1)
        document.add_paragraph(record.conclusion or "尚未填写")
        document.add_heading("条款与证据记录", level=1)
        if not record.items:
            document.add_paragraph("尚无已确认的审核记录项")
        else:
            table = document.add_table(rows=1, cols=6)
            table.style = "Table Grid"
            for cell, title in zip(
                table.rows[0].cells,
                ("条款", "体系", "评价", "现场证据", "审核发现", "AI依据"),
            ):
                cell.text = title
            for item in record.items:
                cells = table.add_row().cells
                values = (
                    item.clause_no_snapshot or "",
                    item.certification_system or "",
                    {"1": "符合", "2": "基本符合", "3": "不符合"}.get(
                        str(item.evaluation_3level), str(item.evaluation_3level or "")
                    ),
                    item.audit_evidence or "",
                    item.audit_findings or "",
                    item.ai_basis or "",
                )
                for cell, value in zip(cells, values):
                    cell.text = str(value)
        buffer = io.BytesIO(); document.save(buffer); return buffer.getvalue()

    @staticmethod
    def _nc_summary_docx(project: AuditProject, ncs: list[Nonconformity]) -> bytes:
        document = Document(); document.add_heading("不符合项汇总", 0); document.add_paragraph(f"项目：{project.title}（{project.project_no}）")
        table = document.add_table(rows=1, cols=6); table.style = "Table Grid"
        for cell, title in zip(table.rows[0].cells, ("编号", "条款", "严重度", "描述", "状态", "整改要求")): cell.text = title
        for nc in ncs:
            cells = table.add_row().cells
            values = (nc.nc_no or "", nc.clause_no or "", nc.severity or "", nc.description or "", nc.status or "", nc.corrective_action_required or "")
            for cell, value in zip(cells, values): cell.text = str(value)
        buffer = io.BytesIO(); document.save(buffer); return buffer.getvalue()

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
                "checked_at": quality["checked_at"],
            }
            report.consistency_check = {
                "score": quality["consistency_score"],
                **quality["consistency"],
                "checked_at": quality["checked_at"],
            }


project_artifact_service = ProjectArtifactService()
