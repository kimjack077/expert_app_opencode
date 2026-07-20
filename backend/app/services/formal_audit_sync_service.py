"""Bridge legacy inspection tasks into the formal audit project record."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit_project import (
    AuditArea,
    AuditAreaRecord,
    AuditPlanItem,
    Nonconformity,
)
from app.models.record import InspectionRecordItem
from app.models.task import InspectionTask, TaskItemRecord
from app.models.user import User


def legacy_result_to_evaluation(result: str | None) -> str | None:
    """Normalize result values used by every legacy task client."""

    normalized = str(result or "").strip().lower()
    if normalized in {"n/a", "na", "not_applicable", "不适用"}:
        return None
    failure_values = {
        "3",
        "fail",
        "failed",
        "non_compliant",
        "nonconformity",
        "pending_rectification",
        "unqualified",
    }
    pass_values = {"1", "compliant", "pass", "passed", "qualified"}
    if normalized in failure_values:
        return "3"
    if normalized in pass_values:
        return "1"
    return "2"


async def get_linked_plan_item(
    db: AsyncSession,
    task_id: UUID,
) -> AuditPlanItem | None:
    return (
        await db.execute(
            select(AuditPlanItem).where(
                AuditPlanItem.inspection_task_id == task_id,
                AuditPlanItem.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()


async def can_access_linked_task(
    db: AsyncSession,
    task: InspectionTask,
    user: User,
) -> bool:
    if user.role in {"admin", "super_admin"}:
        return True
    if str(task.assigned_to or "") == str(user.id):
        return True
    plan_item = await get_linked_plan_item(db, task.id)
    return bool(
        plan_item
        and any(str(value) == str(user.id) for value in plan_item.assigned_member_ids or [])
    )


async def sync_task_to_formal_record(
    db: AsyncSession,
    task: InspectionTask,
    plan_item: AuditPlanItem,
    recorded_by: UUID,
) -> AuditAreaRecord:
    """Idempotently copy completed task rows into one formal area record."""

    source_rows = (
        await db.execute(
            select(TaskItemRecord)
            .where(TaskItemRecord.task_id == task.id)
            .options(
                selectinload(TaskItemRecord.template_item),
                selectinload(TaskItemRecord.media_files),
            )
            .order_by(TaskItemRecord.recorded_at)
        )
    ).scalars().unique().all()
    completed_rows = [
        row
        for row in source_rows
        if str(row.result or "").strip()
        or str(row.result_value or "").strip()
        or str(row.result_text or "").strip()
        or str(row.inspector_note or "").strip()
    ]
    if not completed_rows:
        raise ValueError("请先完成至少一项检查记录，再提交任务")
    if any(not row.template_item_id for row in completed_rows):
        raise ValueError("检查记录存在未关联模板项的数据，请先修复后再提交")
    template_item_ids = [str(row.template_item_id) for row in completed_rows]
    if len(template_item_ids) != len(set(template_item_ids)):
        raise ValueError("同一模板项存在重复检查记录，请先合并后再提交")

    # Serialize completion of the same plan item. This prevents two clients
    # from both observing no formal record and creating duplicates.
    await db.execute(
        select(AuditPlanItem.id)
        .where(AuditPlanItem.id == plan_item.id)
        .with_for_update()
    )

    area = (
        await db.execute(
            select(AuditArea)
            .where(
                AuditArea.project_id == plan_item.project_id,
                AuditArea.area_name == plan_item.area_name,
            )
            .order_by(AuditArea.created_at.desc())
            .limit(1)
        )
    ).scalars().first()
    if not area:
        area = AuditArea(
            project_id=plan_item.project_id,
            area_name=plan_item.area_name,
            area_type=plan_item.area_type,
            responsible_team_member_ids=plan_item.assigned_member_ids or [],
            audit_clauses=plan_item.clauses or [],
            status="in_progress",
        )
        db.add(area)
        await db.flush()

    area_record = (
        await db.execute(
            select(AuditAreaRecord)
            .where(
                AuditAreaRecord.project_id == plan_item.project_id,
                AuditAreaRecord.plan_item_id == plan_item.id,
            )
            .options(selectinload(AuditAreaRecord.items))
            .order_by(AuditAreaRecord.created_at.desc())
            .limit(1)
        )
    ).scalars().first()
    if not area_record:
        existing_items = []
        area_record = AuditAreaRecord(
            project_id=plan_item.project_id,
            area_id=area.id,
            plan_item_id=plan_item.id,
            record_no=f"LEG-{str(task.task_no or task.id)[:40]}",
            template_id=plan_item.template_id,
            certification_systems=plan_item.certification_systems or [],
            recorded_by=recorded_by,
            audit_date=plan_item.plan_date,
            audit_time_start=plan_item.time_start,
            audit_time_end=plan_item.time_end,
            status="in_progress",
        )
        db.add(area_record)
        await db.flush()
    else:
        existing_items = list(area_record.items or [])

    existing_by_template = {
        str(item.template_item_id): item
        for item in existing_items
        if item.template_item_id
    }
    for source in completed_rows:
        template = source.template_item
        evaluation = legacy_result_to_evaluation(source.result)
        evidence = str(source.result_text or source.inspector_note or "").strip()
        if not evidence:
            displayed_result = source.result_value or source.result or "已检查"
            if evaluation is None:
                displayed_result = "不适用"
            evidence = f"{getattr(template, 'title', None) or '检查项'}：{displayed_result}"
        formal = existing_by_template.get(str(source.template_item_id))
        if not formal:
            formal = InspectionRecordItem(
                audit_area_record_id=area_record.id,
                template_item_id=source.template_item_id,
            )
            db.add(formal)
            await db.flush()
            if source.template_item_id:
                existing_by_template[str(source.template_item_id)] = formal

        check_type = getattr(template, "check_type", None) or "audit_3level"
        result_type = getattr(template, "result_type", None) or "pass_fail"
        formal.result = (
            "not_applicable"
            if evaluation is None
            else "fail" if evaluation == "3" else "pass"
        )
        formal.radio_value = source.result
        formal.result_value = source.result_value
        formal.numeric_value = source.result_value if result_type == "numeric" else None
        formal.score_value = source.result_value if result_type == "score" else None
        formal.text_value = source.result_text if result_type == "text" else None
        formal.result_text = source.result_text or evidence
        formal.inspector_note = source.inspector_note
        formal.audit_evidence = evidence
        formal.evaluation_3level = evaluation
        formal.audit_findings = evidence if evaluation == "3" else None
        formal.problem_description = formal.audit_findings
        formal.certification_system = (
            (getattr(template, "applicable_systems", None) or [None])[0]
            or (plan_item.certification_systems or [None])[0]
        )
        clause_snapshot = (
            getattr(template, "clause_no", None)
            or getattr(template, "standard_ref", None)
            or getattr(template, "title", None)
        )
        formal.clause_no_snapshot = str(clause_snapshot)[:50] if clause_snapshot else None
        formal.item_title = getattr(template, "title", None)
        formal.item_description = getattr(template, "description", None)
        formal.item_check_method = getattr(template, "check_method", None)
        formal.item_legal_basis = getattr(template, "legal_basis", None)
        formal.item_standard_ref = getattr(template, "standard_ref", None)
        formal.item_risk_level = getattr(template, "risk_level", None)
        formal.item_check_type = check_type
        formal.item_result_options = getattr(template, "result_options", None)
        formal.item_min_value = getattr(template, "min_value", None)
        formal.item_max_value = getattr(template, "max_value", None)
        formal.item_unit = getattr(template, "unit", None)
        formal.item_score_weight = getattr(template, "score_weight", None)
        formal.item_default_score = getattr(template, "default_score", None)
        formal.item_allow_attachment = bool(getattr(template, "allow_attachment", False))
        formal.item_attachment_required = bool(getattr(template, "attachment_required", False))
        formal.item_ai_prompt_template = getattr(template, "ai_prompt_template", None)
        formal.item_use_ai = bool(getattr(template, "use_ai", False))
        formal.ai_generated = False
        formal.ai_suggestion = source.llm_suggestion
        formal.ai_basis = source.llm_basis
        formal.photos = [
            media.file_path
            for media in source.media_files or []
            if not getattr(media, "is_deleted", False)
        ]

        if evaluation == "3":
            existing_nc = (
                await db.execute(
                    select(Nonconformity.id).where(
                        Nonconformity.record_item_id == formal.id
                    )
                )
            ).scalar_one_or_none()
            if not existing_nc:
                db.add(
                    Nonconformity(
                        project_id=plan_item.project_id,
                        plan_item_id=plan_item.id,
                        area_record_id=area_record.id,
                        record_item_id=formal.id,
                        nc_no=f"LEG-{str(source.id)[:8].upper()}",
                        severity="minor",
                        certification_system=formal.certification_system,
                        clause_no=formal.clause_no_snapshot,
                        description=formal.audit_findings or evidence,
                        evidence=evidence,
                        corrective_action_required="请分析原因并完成整改",
                        status="draft",
                        created_by=recorded_by,
                    )
                )

    now = datetime.now(timezone.utc)
    area_record.conclusion = task.remarks or f"本区域完成 {len(completed_rows)} 项现场检查记录。"
    area_record.status = "submitted"
    area.status = "completed"
    plan_item.status = "completed"
    task.status = "completed"
    task.completed_at = task.completed_at or now
    await db.flush()
    return area_record
