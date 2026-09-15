import json
import re
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.task import InspectionTask, TaskItemRecord
from app.models.media import MediaFile
from app.models.template import InspectionTemplate, TemplateItem
from app.schemas import (
    ApiResponse,
    InspectionTaskCreate,
    InspectionTaskUpdate,
    InspectionTaskResponse,
    InspectionRecordCreate,
    InspectionRecordUpdate,
    InspectionRecordResponse,
    InspectionSummary,
)
from app.utils.security import get_current_user, get_current_admin_user
from app.utils.roles import RECORD_VIEW_ALL_ROLES
from app.utils.category import is_category_node, load_parent_ids
from app.services import AuditService
from app.services.formal_audit_sync_service import (
    can_access_linked_task,
    get_linked_plan_item,
    sync_task_to_formal_record,
)
from app.services.llm_service import llm_service

# Alias for backward compatibility
InspectionRecord = TaskItemRecord

router = APIRouter()


def make_response(data=None, code=200, message="success"):
    return ApiResponse(
        code=code, message=message, data=data, timestamp=datetime.now(timezone.utc)
    )


@router.get("", response_model=ApiResponse)
async def get_tasks(
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 条件构建一次，分页与计数共用，保证 total 与实际可见数据一致
    conditions = [InspectionTask.is_deleted == False]  # noqa: E712

    if current_user.role not in RECORD_VIEW_ALL_ROLES:
        conditions.append(InspectionTask.assigned_to == current_user.id)

    if status:
        conditions.append(InspectionTask.status == status)

    query = (
        select(InspectionTask)
        .where(*conditions)
        .order_by(InspectionTask.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    tasks = result.scalars().all()

    total = (
        await db.execute(select(func.count(InspectionTask.id)).where(*conditions))
    ).scalar() or 0

    # BUG-05：批量回填审核计划项关联字段（此前列表接口 plan_item_id/audit_project_id 恒为 null，
    # 与详情接口口径不一致），保证 Web / H5 任务卡片能展示所属项目与区域。
    from app.models.audit_project import AuditPlanItem

    plan_map: dict = {}
    task_ids = [t.id for t in tasks]
    if task_ids:
        plan_rows = await db.execute(
            select(AuditPlanItem).where(
                AuditPlanItem.inspection_task_id.in_(task_ids),
                AuditPlanItem.is_deleted == False,  # noqa: E712
            )
        )
        for pi in plan_rows.scalars().all():
            if pi.inspection_task_id:
                plan_map.setdefault(str(pi.inspection_task_id), pi)

    items = []
    for t in tasks:
        data = InspectionTaskResponse.model_validate(t).model_dump()
        pi = plan_map.get(str(t.id))
        if pi:
            data["audit_project_id"] = pi.project_id
            data["plan_item_id"] = pi.id
            data["area_name"] = pi.area_name
            data["clauses"] = pi.clauses
        items.append(data)

    return make_response(data={"items": items, "total": total})


@router.get("/statistics", response_model=ApiResponse)
async def get_task_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """任务状态统计。

    与列表接口使用完全一致的可见范围，供 H5 顶部汇总使用，
    避免前端基于分页数组累加导致「已完成 > 总数」的口径错误。
    """
    conditions = [InspectionTask.is_deleted == False]  # noqa: E712
    if current_user.role not in RECORD_VIEW_ALL_ROLES:
        conditions.append(InspectionTask.assigned_to == current_user.id)

    rows = await db.execute(
        select(InspectionTask.status, func.count(InspectionTask.id))
        .where(*conditions)
        .group_by(InspectionTask.status)
    )
    counts = {(status or "unknown"): count for status, count in rows.all()}
    total = sum(counts.values())

    return make_response(
        data={
            "total": total,
            "pending": counts.get("pending", 0),
            "in_progress": counts.get("in_progress", 0),
            "completed": counts.get("completed", 0),
            "cancelled": counts.get("cancelled", 0),
        }
    )


@router.post("", response_model=ApiResponse)
async def create_task(
    task_data: InspectionTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    # 不能用 count(*)+1：并发创建会生成相同编号（且会把软删行计入，删除后编号回退重复）。
    # 改用随机短码，保证唯一且无需额外往返。
    task_no = f"TASK-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"

    task = InspectionTask(
        task_no=task_no,
        title=task_data.title,
        template_id=task_data.template_id,
        assigned_to=task_data.assigned_to,
        assigned_by=current_user.id,
        target_name=task_data.target_name,
        target_address=task_data.target_address,
        target_contact=task_data.target_contact,
        target_phone=task_data.target_phone,
        scheduled_at=task_data.scheduled_at,
        remarks=task_data.remarks,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    if task_data.template_id:
        # 分类目录（存在有效子节点的父节点）集合，统一走 app/utils/category
        parent_ids = await load_parent_ids(db, template_id=task_data.template_id)

        items_result = await db.execute(
            select(TemplateItem)
            .where(
                TemplateItem.template_id == task_data.template_id,
                TemplateItem.is_deleted == False,  # noqa: E712
                TemplateItem.is_category.is_not(True),
            )
            .order_by(TemplateItem.sort_order)
        )
        # 严格只为真正的叶子检查项创建填报记录，杜绝分类目录生成空记录
        leaf_items = [
            i for i in items_result.scalars().all()
            if not is_category_node(i, parent_ids)
        ]

        for item in leaf_items:
            record = InspectionRecord(
                task_id=task.id,
                template_item_id=item.id,
            )
            db.add(record)
        await db.commit()

    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "create_task",
        "task",
        str(task.id),
    )

    return make_response(data=InspectionTaskResponse.model_validate(task).model_dump())


@router.get("/{task_id}", response_model=ApiResponse)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(InspectionTask, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    if current_user.role == "expert" and not await can_access_linked_task(db, task, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to view this task")

    # 查询关联的审核计划项信息，并兼容回填缺失的 template_id
    plan_item = None
    try:
        from app.models.audit_project import AuditPlanItem

        task_uuid = UUID(str(task_id))
        plan_result = await db.execute(
            select(AuditPlanItem).where(
                AuditPlanItem.inspection_task_id == task_uuid,
                AuditPlanItem.is_deleted == False,  # noqa: E712
            )
        )
        plan_item = plan_result.scalar_one_or_none()
        if plan_item and not task.template_id and plan_item.template_id:
            task.template_id = plan_item.template_id
            await db.commit()
            await db.refresh(task)
    except Exception:
        # 容错处理
        pass

    data = InspectionTaskResponse.model_validate(task).model_dump()
    if plan_item:
        data["audit_project_id"] = plan_item.project_id
        data["plan_item_id"] = plan_item.id
        data["area_name"] = plan_item.area_name
        data["clauses"] = plan_item.clauses

    # BUG-32：补充指派对象姓名，避免 H5 详情页误显示"未分配"
    if task.assigned_to:
        assignee = await db.get(User, task.assigned_to)
        if assignee and not assignee.is_deleted:
            data["assigned_to_name"] = assignee.full_name or assignee.username

    return make_response(data=data)


@router.put("/{task_id}", response_model=ApiResponse)
async def update_task(
    task_id: str,
    task_data: InspectionTaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.audit_project import AuditPlanItem, AuditProject

    task = await db.get(InspectionTask, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    # 专家用户只能更新分配给自己的任务状态与备注
    if current_user.role == "expert":
        if not await can_access_linked_task(db, task, current_user):
            raise HTTPException(status_code=403, detail="Not authorized to update this task")
        # BUG-31：remarks 此前被静默丢弃，导致 H5 提交流程
        # （updateTask 写"最终判定: xx"备注 → POST /complete）必然 409。
        # 专家仅允许更新 remarks，其余字段仍不可改。
        if task_data.remarks is not None:
            task.remarks = task_data.remarks
        if task_data.status:
            # 与 POST /{task_id}/complete 同一口径：没有最终判定结论不允许置为已完成
            if task_data.status == "completed" and not re.search(
                r"最终判定\s*[:：]\s*(pass|fail|partial_pass|合格|不合格|基本合格|符合|不符合)",
                task.remarks or "",
                re.IGNORECASE,
            ):
                raise HTTPException(
                    status_code=409,
                    detail="请先填写最终判定结论（合格/基本合格/不合格），再完成任务",
                )
            task.status = task_data.status
            if task_data.status == "in_progress":
                task.started_at = datetime.now(timezone.utc)
            elif task_data.status == "completed":
                task.completed_at = datetime.now(timezone.utc)
                # 检查是否有关联的审核计划项
                try:
                    task_uuid = UUID(task_id)
                    plan_item_result = await db.execute(
                        select(AuditPlanItem).where(AuditPlanItem.inspection_task_id == task_uuid)
                    )
                    plan_item = plan_item_result.scalar_one_or_none()
                except ValueError:
                    plan_item = None
                if plan_item:
                    plan_item.status = "completed"
                    await _sync_project_status_after_plan_item(db, plan_item.project_id)
    else:
        # 管理员可以更新所有字段
        update_data = task_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(task, key, value)
        # 与专家分支同一口径：没有最终判定结论不允许置为已完成
        #（setattr 已应用，task.remarks 即为合并后的备注）
        if task_data.status == "completed" and not re.search(
            r"最终判定\s*[:：]\s*(pass|fail|partial_pass|合格|不合格|基本合格|符合|不符合)",
            task.remarks or "",
            re.IGNORECASE,
        ):
            raise HTTPException(
                status_code=409,
                detail="请先填写最终判定结论（合格/基本合格/不合格），再完成任务",
            )
        # 如果管理员更新状态为 completed，也要同步审核计划项
        if task_data.status == "completed":
            task.completed_at = datetime.now(timezone.utc)
            try:
                task_uuid = UUID(task_id)
                plan_item_result = await db.execute(
                    select(AuditPlanItem).where(AuditPlanItem.inspection_task_id == task_uuid)
                )
                plan_item = plan_item_result.scalar_one_or_none()
            except ValueError:
                plan_item = None
            if plan_item:
                plan_item.status = "completed"
                await _sync_project_status_after_plan_item(db, plan_item.project_id)

    # Older clients complete tasks through PUT instead of POST /complete.
    # Route both paths through the formal-record bridge before committing.
    if task_data.status == "completed":
        try:
            linked_plan_item = await get_linked_plan_item(db, UUID(task_id))
        except ValueError:
            linked_plan_item = None
        if linked_plan_item:
            try:
                await sync_task_to_formal_record(
                    db,
                    task,
                    linked_plan_item,
                    current_user.id,
                )
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc

    await db.commit()
    await db.refresh(task)

    return make_response(data=InspectionTaskResponse.model_validate(task).model_dump())


@router.post("/{task_id}/start", response_model=ApiResponse)
async def start_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.audit_project import AuditPlanItem, AuditProject

    task = await db.get(InspectionTask, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    # 管理员可以启动任何任务，专家只能启动分配给自己的任务
    if current_user.role == "expert" and not await can_access_linked_task(db, task, current_user):
        raise HTTPException(status_code=403, detail="Not assigned to you")

    if task.status != "pending":
        raise HTTPException(status_code=400, detail="Task cannot be started")

    task.status = "in_progress"
    task.started_at = datetime.now(timezone.utc)

    # 检查是否有关联的审核计划项，更新为进行中状态
    try:
        task_uuid = UUID(task_id)
        plan_item_result = await db.execute(
            select(AuditPlanItem).where(AuditPlanItem.inspection_task_id == task_uuid)
        )
        plan_item = plan_item_result.scalar_one_or_none()
    except ValueError:
        plan_item = None
    if plan_item:
        plan_item.status = "in_progress"
        # 更新审核项目状态
        project = await db.get(AuditProject, plan_item.project_id)
        if project and project.status == "planning":
            project.status = "in_progress"

    await db.commit()

    await AuditService.log_action(
        db, str(current_user.id), current_user.username, "start_task", "task", task_id
    )

    return make_response(message="Task started")


async def _sync_project_status_after_plan_item(db: AsyncSession, project_id) -> None:
    """计划项完成后回写审核项目状态。

    规则：
    - 还有未完成的计划项 → 项目置为进行中
    - 全部计划项完成 → 项目置为已完成，并补记 actual_end

    原实现只在任务开始时把项目置为 in_progress，**没有任何地方置 completed**，
    导致审核统计里「已完成」永远是 0（测试问题清单第 16 条）。
    """
    if not project_id:
        return

    from app.models.audit_project import AuditPlanItem, AuditProject

    project = await db.get(AuditProject, project_id)
    if not project or project.is_deleted:
        return
    # 已取消/已完成的项目不再被回写覆盖
    if project.status in ("cancelled", "completed"):
        return

    remaining = (
        await db.execute(
            select(func.count(AuditPlanItem.id)).where(
                AuditPlanItem.project_id == project_id,
                AuditPlanItem.is_deleted == False,  # noqa: E712
                AuditPlanItem.status != "completed",
            )
        )
    ).scalar() or 0

    if remaining == 0:
        project.status = "completed"
        if not project.actual_end:
            project.actual_end = datetime.now(timezone.utc)
    elif project.status == "planning":
        project.status = "in_progress"


@router.post("/{task_id}/complete", response_model=ApiResponse)
async def complete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(InspectionTask, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    if current_user.role == "expert" and not await can_access_linked_task(
        db, task, current_user
    ):
        raise HTTPException(status_code=403, detail="Not assigned to you")

    if task.status == "completed":
        raise HTTPException(status_code=409, detail="任务已完成，不能重复提交")

    # BUG-11：完成前校验必填检查项覆盖率必须 100%，杜绝"空任务直接完成"
    records_res = await db.execute(
        select(TaskItemRecord)
        .options(selectinload(TaskItemRecord.template_item))
        .where(TaskItemRecord.task_id == task.id)
    )
    missing: list[str] = []
    for rec in records_res.scalars().all():
        tpl_item = getattr(rec, "template_item", None)
        if not tpl_item or not bool(tpl_item.is_required):
            continue
        filled = bool(rec.result or rec.result_value or rec.result_text)
        if not filled:
            missing.append(getattr(tpl_item, "title", "") or str(rec.template_item_id))
    if missing:
        preview = "、".join(missing[:3])
        suffix = f" 等 {len(missing)} 项" if len(missing) > 3 else ""
        raise HTTPException(
            status_code=409,
            detail=f"存在未填报的必填检查项，无法完成任务：{preview}{suffix}",
        )

    # 最终判定结论必填：任务模式把结论写在 remarks 里（`最终判定:合格 | 判定说明:...`）。
    # 原先不校验，未选判定结果也能完成任务，落库一批没有结论的「已完成」任务。
    if not re.search(
        r"最终判定\s*[:：]\s*(pass|fail|partial_pass|合格|不合格|基本合格|符合|不符合)",
        task.remarks or "",
        re.IGNORECASE,
    ):
        raise HTTPException(
            status_code=409,
            detail="请先填写最终判定结论（合格/基本合格/不合格），再完成任务",
        )

    try:
        task_uuid = UUID(task_id)
        plan_item = await get_linked_plan_item(db, task_uuid)
    except ValueError:
        plan_item = None

    if plan_item:
        try:
            await sync_task_to_formal_record(
                db,
                task,
                plan_item,
                current_user.id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        # 计划项完成后回写项目状态（全部完成 → 项目已完成）
        await _sync_project_status_after_plan_item(db, plan_item.project_id)
    else:
        task.status = "completed"
        task.completed_at = datetime.now(timezone.utc)

    await db.commit()

    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "complete_task",
        "task",
        task_id,
    )

    return make_response(message="Task completed")


@router.delete("/{task_id}", response_model=ApiResponse)
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除检查任务（仅管理员可删除，软删除）"""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Only admin can delete tasks")

    task = await db.get(InspectionTask, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    from app.utils.soft_delete import soft_delete

    await soft_delete(db, task, unique_fields=["task_no"])
    await db.commit()

    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "delete_task",
        "task",
        task_id,
    )

    return make_response(message="Task deleted")


@router.get("/{task_id}/records", response_model=ApiResponse)
async def get_task_records(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(InspectionTask, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    if current_user.role == "expert" and not await can_access_linked_task(db, task, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(InspectionRecord)
        .options(selectinload(InspectionRecord.template_item))
        .where(InspectionRecord.task_id == task_id)
        .order_by(InspectionRecord.recorded_at)
    )
    records = result.scalars().all()

    # 任务已关联模板但没有可用检查项时，按模板自动补齐（兼容历史脏数据）
    has_linked_items = any(r.template_item_id for r in records)
    template_parent_ids = set()
    if task.template_id:
        template_parent_ids = await load_parent_ids(db, template_id=task.template_id)

    if task.template_id and not has_linked_items:
        items_result = await db.execute(
            select(TemplateItem)
            .where(
                TemplateItem.template_id == task.template_id,
                TemplateItem.is_deleted == False,  # noqa: E712
                TemplateItem.is_category.is_not(True),
            )
            .order_by(TemplateItem.sort_order)
        )
        template_items = [
            i for i in items_result.scalars().all()
            if not is_category_node(i, template_parent_ids)
        ]
        if template_items:
            # 清理无模板项关联的空记录，避免干扰
            for empty_rec in records:
                if not empty_rec.template_item_id and not empty_rec.result:
                    await db.delete(empty_rec)
            for item in template_items:
                db.add(
                    InspectionRecord(
                        task_id=task.id,
                        template_item_id=item.id,
                    )
                )
            await db.commit()
            result = await db.execute(
                select(InspectionRecord)
                .options(selectinload(InspectionRecord.template_item))
                .where(InspectionRecord.task_id == task_id)
                .order_by(InspectionRecord.recorded_at)
            )
            records = result.scalars().all()

    # 一次性取出本任务所有附件，按检查项分组。
    # 原实现不返回附件，前端 photos 只能恒为空，导致「上传后再次查看附件丢失」。
    record_ids = [r.id for r in records]
    photos_by_record: dict = {}
    if record_ids:
        media_rows = await db.execute(
            select(MediaFile.record_id, MediaFile.file_path)
            .where(
                MediaFile.record_id.in_(record_ids),
                MediaFile.is_deleted == False,  # noqa: E712
            )
            .order_by(MediaFile.uploaded_at)
        )
        for rec_id, file_path in media_rows.all():
            if rec_id and file_path:
                photos_by_record.setdefault(rec_id, []).append(file_path)

    payload = []
    for r in records:
        ti = r.template_item
        if ti is not None:
            # 分类目录一律不参与检查项统计与展示：
            # 不论历史上是否被误填过结果，都不能作为检查项返回，
            # 否则条目总数会与模板叶子口径对不上（P0-02 / P0-03）。
            if is_category_node(ti, template_parent_ids):
                continue
            # 模板条目已被软删除且本记录未填写 → 孤儿空记录，一并剔除
            if ti.is_deleted and not r.result:
                continue

        item = InspectionRecordResponse.model_validate(r).model_dump()
        # 附件（现场照片等）随记录一起返回，供前端回显
        item["photos"] = photos_by_record.get(r.id, [])
        if r.template_item is not None:
            check_item = {
                "id": str(r.template_item.id),
                "title": r.template_item.title,
                "description": r.template_item.description,
                "check_method": r.template_item.check_method,
                "legal_basis": r.template_item.legal_basis,
                "standard_ref": r.template_item.standard_ref,
                "clause_no": r.template_item.clause_no,
                "template_id": str(r.template_item.template_id)
                if r.template_item.template_id
                else None,
                "is_category": bool(r.template_item.is_category),
                "result_type": r.template_item.result_type,
                "check_type": r.template_item.check_type,
                "result_options": r.template_item.result_options,
                "is_required": r.template_item.is_required,
                "attachment_required": bool(r.template_item.attachment_required),
                "allow_attachment": bool(r.template_item.allow_attachment)
                if r.template_item.allow_attachment is not None
                else True,
                "unit": r.template_item.unit,
                "parent_id": str(r.template_item.parent_id)
                if r.template_item.parent_id
                else None,
                "sort_order": r.template_item.sort_order
                if r.template_item.sort_order is not None
                else 0,
                "min_value": float(r.template_item.min_value)
                if r.template_item.min_value is not None
                else None,
                "max_value": float(r.template_item.max_value)
                if r.template_item.max_value is not None
                else None,
                "max_score": float(r.template_item.max_score)
                if r.template_item.max_score is not None
                else None,
                "score_step": float(r.template_item.score_step)
                if r.template_item.score_step is not None
                else None,
                "pass_score": float(r.template_item.pass_score)
                if r.template_item.pass_score is not None
                else None,
            }
            item["template_item"] = check_item
            # 兼容旧前端字段名 check_item
            item["check_item"] = check_item
        payload.append(item)

    # 先按模板 sort_order 排序，再按父子层级展开为树序（避免分类节点与子项错位）
    def _item_meta(raw):
        return raw.get("template_item") or raw.get("check_item") or {}

    children_by_parent = {}
    for item in payload:
        parent_key = _item_meta(item).get("parent_id")
        children_by_parent.setdefault(parent_key, []).append(item)
    for key in children_by_parent:
        children_by_parent[key].sort(
            key=lambda x: _item_meta(x).get("sort_order", 0) or 0
        )

    ordered = []

    def _walk(parent_key):
        for node in children_by_parent.get(parent_key, []):
            ordered.append(node)
            _walk(_item_meta(node).get("id"))

    _walk(None)

    if len(ordered) != len(payload):
        # 兜底：存在父节点缺失的孤儿项时，按 sort_order 追加，避免条目被丢弃
        seen = {id(node) for node in ordered}
        ordered.extend(
            sorted(
                (x for x in payload if id(x) not in seen),
                key=lambda x: _item_meta(x).get("sort_order", 0) or 0,
            )
        )

    payload = ordered

    return make_response(data=payload)


@router.post("/{task_id}/records", response_model=ApiResponse)
async def create_or_update_record(
    task_id: str,
    record_data: InspectionRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(InspectionTask, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    # 管理员可以为任何任务创建记录，专家只能为分配给自己的任务创建记录
    if current_user.role == "expert" and not await can_access_linked_task(db, task, current_user):
        raise HTTPException(status_code=403, detail="Not assigned to you")

    # BUG-11：已完成的任务填报记录为只读，防止事后篡改
    if task.status == "completed":
        raise HTTPException(status_code=409, detail="任务已完成，填报记录不可再修改")

    if record_data.template_item_id:
        result = await db.execute(
            select(InspectionRecord).where(
                InspectionRecord.task_id == task_id,
                InspectionRecord.template_item_id == record_data.template_item_id,
            )
        )
        record = result.scalar_one_or_none()

        if record:
            if record_data.result is not None:
                record.result = record_data.result
            if record_data.result_value is not None:
                record.result_value = record_data.result_value
            if record_data.result_text is not None:
                record.result_text = record_data.result_text
            if record_data.inspector_note is not None:
                record.inspector_note = record_data.inspector_note
            record.updated_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(record)
            return make_response(
                data=InspectionRecordResponse.model_validate(record).model_dump()
            )

    record = InspectionRecord(
        task_id=task_id,
        template_item_id=record_data.template_item_id,
        result=record_data.result,
        result_value=record_data.result_value,
        result_text=record_data.result_text,
        inspector_note=record_data.inspector_note,
        recorded_by=current_user.id,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return make_response(
        data=InspectionRecordResponse.model_validate(record).model_dump()
    )


@router.put("/records/{record_id}", response_model=ApiResponse)
async def update_record(
    record_id: str,
    record_data: InspectionRecordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await db.get(InspectionRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    # 默认拒绝：父任务缺失（孤儿记录）时不能放行，否则任何登录用户都能改
    task = await db.get(InspectionTask, record.task_id) if record.task_id else None
    if not task:
        raise HTTPException(status_code=404, detail="Parent task not found")
    if current_user.role == "expert" and not await can_access_linked_task(db, task, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    # BUG-11：已完成的填报记录为只读，防止事后篡改
    if task.status == "completed":
        raise HTTPException(status_code=409, detail="任务已完成，填报记录不可再修改")

    update_data = record_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(record, key, value)
    record.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(record)

    return make_response(
        data=InspectionRecordResponse.model_validate(record).model_dump()
    )


@router.get("/{task_id}/summary", response_model=ApiResponse)
async def get_task_summary(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(InspectionTask, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    # 与 get_task / get_task_records 保持一致的访问控制（原先缺失导致可越权读他人任务汇总）
    if current_user.role == "expert" and not await can_access_linked_task(db, task, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(InspectionRecord)
        .options(selectinload(InspectionRecord.template_item))
        .where(InspectionRecord.task_id == task_id)
    )
    records = result.scalars().all()

    def _is_pass(result: Optional[str]) -> bool:
        return result in {"compliant", "pass", "qualified", "1"}

    def _is_fail(result: Optional[str]) -> bool:
        return result in {"non_compliant", "fail", "unqualified", "3", "pending_rectification"}

    def _is_na(result: Optional[str]) -> bool:
        return result in {"not_applicable", "na", "n/a", "不适用"}

    # 排除分类节点：只要节点下挂着有效子项（或显式标记分类），一律不计入统计；
    # 模板条目已删除且未填写的孤儿记录同样剔除。统一走 app/utils/category。
    parent_ids = (
        await load_parent_ids(db, template_id=task.template_id)
        if task.template_id
        else set()
    )
    countable = []
    for r in records:
        ti = r.template_item
        if ti is not None:
            if is_category_node(ti, parent_ids):
                continue
            if ti.is_deleted and not r.result:
                continue
        countable.append(r)

    total = len(countable)
    completed = sum(1 for r in countable if r.result)
    compliant = sum(1 for r in countable if _is_pass(r.result))
    non_compliant = sum(1 for r in countable if _is_fail(r.result))
    not_applicable = sum(1 for r in countable if _is_na(r.result))

    # 合规率分母仅计有效参评项（剔除不适用/未涉及项）
    applicable_evaluated = compliant + non_compliant
    compliance_rate = (compliant / applicable_evaluated * 100) if applicable_evaluated > 0 else 0

    summary = InspectionSummary(
        total=total,
        completed=completed,
        compliant=compliant,
        non_compliant=non_compliant,
        not_applicable=not_applicable,
        compliance_rate=round(compliance_rate, 2),
    )

    return make_response(data=summary.model_dump())


@router.get("/{task_id}/final-judgment-stream")
async def generate_task_final_judgment_stream(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """流式生成任务最终判定结论（与 H5/Web 任务检查共用 TaskItemRecord 数据链）"""
    task = await db.get(InspectionTask, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    if current_user.role == "expert" and not await can_access_linked_task(db, task, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(TaskItemRecord)
        .options(selectinload(TaskItemRecord.template_item))
        .where(TaskItemRecord.task_id == task_id)
        .order_by(TaskItemRecord.recorded_at)
    )
    task_items = result.scalars().all()

    # 分类目录不参与最终判定统计（含"有子节点但未标分类"的脏数据兜底）
    parent_ids = (
        await load_parent_ids(db, template_id=task.template_id)
        if task.template_id
        else set()
    )

    items_data = []
    for item in task_items:
        template_item = item.template_item
        if template_item is not None:
            if is_category_node(template_item, parent_ids):
                continue
            if template_item.is_deleted and not item.result:
                continue
        title = (
            template_item.title
            if template_item and template_item.title
            else "未知检查项"
        )
        items_data.append(
            {
                "title": title,
                "result": item.result,
                # 任务链字段映射到最终判定摘要使用的统一字段
                "radio_value": item.result,
                "score_value": item.result_value,
                "numeric_value": item.result_value,
                "text_value": item.result_text,
                "multi_value": [],
                "risk_level": template_item.risk_level if template_item else None,
                "problem_description": item.inspector_note,
                "pass_score": getattr(template_item, "pass_score", None)
                if template_item
                else None,
                "max_score": getattr(template_item, "max_score", None)
                if template_item
                else None,
                "min_value": template_item.min_value if template_item else None,
                "max_value": template_item.max_value if template_item else None,
                "unit": template_item.unit if template_item else None,
            }
        )

    template_name = task.title
    if task.template_id:
        template = await db.get(InspectionTemplate, task.template_id)
        if template and not template.is_deleted:
            template_name = template.name

    inspection_date = None
    if task.started_at:
        inspection_date = task.started_at.isoformat()
    elif task.scheduled_at:
        inspection_date = task.scheduled_at.isoformat()
    elif task.created_at:
        inspection_date = task.created_at.isoformat()

    async def generate():
        async for chunk in llm_service.get_final_judgment_stream(
            template_name=template_name,
            inspection_date=inspection_date,
            items=items_data,
        ):
            data = json.dumps(chunk, ensure_ascii=False)
            yield f"data: {data}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{task_id}/records/{record_id}/ai-stream")
async def generate_task_item_ai_stream(
    task_id: str,
    record_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """流式生成任务检查项 AI 建议（record_id 可为 TaskItemRecord.id 或 template_item_id）"""
    task = await db.get(InspectionTask, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    if current_user.role == "expert" and not await can_access_linked_task(db, task, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(TaskItemRecord)
        .options(selectinload(TaskItemRecord.template_item))
        .where(
            TaskItemRecord.task_id == task_id,
            (TaskItemRecord.id == record_id)
            | (TaskItemRecord.template_item_id == record_id),
        )
    )
    record_item = result.scalar_one_or_none()
    if not record_item:
        raise HTTPException(status_code=404, detail="Task item not found")

    template_item = record_item.template_item
    if not template_item:
        raise HTTPException(status_code=400, detail="Template item not found")

    async def generate():
        async for chunk in llm_service.get_suggestion_stream(
            template_item, record_item
        ):
            data = json.dumps(chunk, ensure_ascii=False)
            yield f"data: {data}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
