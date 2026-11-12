"""Bridge legacy inspection tasks into the formal audit project record."""

import re
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
from app.models.record import InspectionRecord, InspectionRecordItem
from app.models.task import InspectionTask, TaskItemRecord
from app.models.user import User
from app.models.template import InspectionTemplate
from app.utils.item_stats import FAIL_VALUES, NA_VALUES, PASS_VALUES
from app.utils.item_completion import resolve_check_type
from app.utils.scoring import calculate_total_score


# 最终判定写在任务 remarks 里（`最终判定:合格 | 判定说明:...`）。
# 必须提取判定值再映射，不能用子串匹配——"合格，无不合格项" 会被误判为 fail。
_JUDGMENT_RE = re.compile(
    r"最终判定\s*[:：]\s*(pass|fail|partial_pass|合格|不合格|基本合格|符合|不符合)",
    re.IGNORECASE,
)
_JUDGMENT_MAP = {
    "pass": "pass",
    "合格": "pass",
    "符合": "pass",
    "partial_pass": "partial_pass",
    "基本合格": "partial_pass",
    "fail": "fail",
    "不合格": "fail",
    "不符合": "fail",
}


def overall_from_remarks(remarks: str | None) -> str | None:
    """从任务备注提取最终判定，无法识别时不推断结论。"""
    match = _JUDGMENT_RE.search(remarks or "")
    if match:
        return _JUDGMENT_MAP.get(match.group(1).lower())
    return None


def legacy_result_to_evaluation(result: str | None) -> str | None:
    """把旧任务客户端的结果值映射为三级评价（1=合格 / 2=观察 / 3=不合格）。

    判定集合统一取自 ``app.utils.item_stats``，不再本地维护别名表。

    注意职责差异：本函数是**评价映射**（产出 1/2/3），
    与 ``item_stats.classify_result`` 的**统计归类**（产出 pass/fail/na）不同——
    ``pending_rectification`` 在此按不合格（3）处理，因为它意味着存在需要整改的
    发现项；而在统计口径中它属中间态，不计入合格/不合格/不适用任一桶。
    """

    normalized = str(result or "").strip().lower()
    if not normalized:
        return None
    if normalized in NA_VALUES:
        return None
    if normalized in FAIL_VALUES or normalized in {"failed", "nonconformity", "pending_rectification"}:
        return "3"
    if normalized in PASS_VALUES or normalized in {"passed"}:
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
        or (row.result_value is not None and str(row.result_value).strip())
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
        synced_items: list = []
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
        synced_items = existing_items

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
            synced_items.append(formal)
            if source.template_item_id:
                existing_by_template[str(source.template_item_id)] = formal

        # 快照类型必须取**真实类型**：template_items.check_type 恒为列默认值 'radio'，
        # 真实类型在 result_type。下方 result_value/numeric_value/text_value 的路由
        # 本就用 result_type，这里与它对齐，避免快照与结果字段互相矛盾。
        check_type = (
            resolve_check_type(template) if template is not None else "audit_3level"
        )
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
    area_record.conclusion = task.remarks or f"\u672c\u533a\u57df\u5b8c\u6210 {len(completed_rows)} \u9879\u73b0\u573a\u68c0\u67e5\u8bb0\u5f55\u3002"
    area_record.status = "submitted"

    # 同步到 inspection_records：「检查记录与报告」菜单读的是这张表，
    # 只写 audit_area_records 会导致日常检查完成后该菜单仍为空。
    marker = f"[task:{task.id}]"
    inspection_record = (
        await db.execute(
            select(InspectionRecord)
            .where(
                InspectionRecord.is_deleted == False,  # noqa: E712
                InspectionRecord.remarks.like(f"%{marker}%"),
            )
            .order_by(InspectionRecord.created_at.desc())
            .limit(1)
        )
    ).scalars().first()
    # BUG-FIX: 不要直接访问 plan_item.project，会触发懒加载导致 MissingGreenlet 错误
    # 始终通过 project_id 异步加载
    project = None
    if plan_item.project_id:
        from app.models.audit_project import AuditProject

        project = await db.get(AuditProject, plan_item.project_id)

    # BUG-FIX: 同样不要访问 project.enterprise，也会触发懒加载
    # 通过 project.enterprise_id 异步加载
    enterprise = None
    if project and project.enterprise_id:
        from app.models.enterprise import Enterprise

        enterprise = await db.get(Enterprise, project.enterprise_id)
    overall = overall_from_remarks(task.remarks)
    synced_remarks = f"{marker} 由日常检查任务 {task.task_no} 完成时同步 | {task.remarks or ''}".strip()
    if not inspection_record:
        if overall is None:
            raise ValueError("请先填写最终判定结论（合格/基本合格/不合格），再完成任务")
        inspection_record = InspectionRecord(
            template_id=plan_item.template_id,
            enterprise_id=getattr(enterprise, "id", None),
            enterprise_name=(
                getattr(enterprise, "name", None)
                or getattr(project, "title", None)
                or task.target_name
            ),
            enterprise_address=getattr(enterprise, "address", None) or task.target_address,
            contact_person=getattr(enterprise, "contact_person", None) or task.target_contact,
            contact_phone=getattr(enterprise, "contact_phone", None) or task.target_phone,
            inspector_id=recorded_by,
            inspection_date=now,
            status="submitted",
            overall_result=overall,
            remarks=synced_remarks,
            judgment_note=task.remarks,
        )
        db.add(inspection_record)
        await db.flush()
    else:
        inspection_record.status = "submitted"
        if overall is not None:
            inspection_record.overall_result = overall
        inspection_record.remarks = synced_remarks
        inspection_record.judgment_note = task.remarks
        inspection_record.inspector_id = recorded_by

    # 这里必须用同步过程中自己维护的列表，不能访问 ``area_record.items``：
    # 新建的 area_record 在 flush 之后关系集合仍是未加载状态，async 会话里
    # 访问它会触发同步懒加载并抛 MissingGreenlet —— 任务完成接口直接 500，
    # 且此时任务/计划项/正式记录都未提交，用户看到的是"提交失败"。
    for item in synced_items:
        item.record_id = inspection_record.id
    template = await db.get(InspectionTemplate, plan_item.template_id) if plan_item.template_id else None
    inspection_record.total_score = calculate_total_score(synced_items) if template and getattr(template, "is_quantified", False) else None

    area.status = "completed"
    plan_item.status = "completed"
    task.status = "completed"
    task.completed_at = task.completed_at or now
    await db.flush()
    return area_record
