import json
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.task import InspectionTask, TaskItemRecord
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
        code=code, message=message, data=data, timestamp=datetime.utcnow()
    )


@router.get("", response_model=ApiResponse)
async def get_tasks(
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(InspectionTask).where(InspectionTask.is_deleted == False)  # noqa: E712

    if current_user.role == "expert":
        query = query.where(InspectionTask.assigned_to == current_user.id)

    if status:
        query = query.where(InspectionTask.status == status)

    query = query.order_by(InspectionTask.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    tasks = result.scalars().all()

    total = (await db.execute(select(func.count(InspectionTask.id)).where(InspectionTask.is_deleted == False))).scalar()  # noqa: E712

    return make_response(
        data={
            "items": [
                InspectionTaskResponse.model_validate(t).model_dump() for t in tasks
            ],
            "total": total,
        }
    )


@router.post("", response_model=ApiResponse)
async def create_task(
    task_data: InspectionTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    count_result = await db.execute(select(func.count(InspectionTask.id)))
    count = count_result.scalar() or 0
    task_no = f"TASK-{datetime.now().strftime('%Y%m%d')}-{count + 1:04d}"

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
        items_result = await db.execute(
            select(TemplateItem)
            .where(TemplateItem.template_id == task_data.template_id)
            .order_by(TemplateItem.sort_order)
        )
        items = items_result.scalars().all()

        for item in items:
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

    # 兼容历史数据：任务未写 template_id 时，尝试从关联审核计划项回填
    if not task.template_id:
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
            if plan_item and plan_item.template_id:
                task.template_id = plan_item.template_id
                await db.commit()
                await db.refresh(task)
        except Exception:
            # 回填失败不影响任务详情返回
            pass

    return make_response(data=InspectionTaskResponse.model_validate(task).model_dump())


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

    # 专家用户只能更新分配给自己的任务状态
    if current_user.role == "expert":
        if not await can_access_linked_task(db, task, current_user):
            raise HTTPException(status_code=403, detail="Not authorized to update this task")
        # 专家用户只能更新状态
        if task_data.status:
            task.status = task_data.status
            if task_data.status == "in_progress":
                task.started_at = datetime.utcnow()
            elif task_data.status == "completed":
                task.completed_at = datetime.utcnow()
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
                    project = await db.get(AuditProject, plan_item.project_id)
                    if project and project.status == "planning":
                        project.status = "in_progress"
    else:
        # 管理员可以更新所有字段
        update_data = task_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(task, key, value)
        # 如果管理员更新状态为 completed，也要同步审核计划项
        if task_data.status == "completed":
            task.completed_at = datetime.utcnow()
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
                project = await db.get(AuditProject, plan_item.project_id)
                if project and project.status == "planning":
                    project.status = "in_progress"

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
    task.started_at = datetime.utcnow()

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
    else:
        task.status = "completed"
        task.completed_at = datetime.utcnow()

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
    if task.template_id and not has_linked_items:
        items_result = await db.execute(
            select(TemplateItem)
            .where(
                TemplateItem.template_id == task.template_id,
                TemplateItem.is_deleted == False,  # noqa: E712
                TemplateItem.is_category != True,  # noqa: E712
            )
            .order_by(TemplateItem.sort_order)
        )
        template_items = items_result.scalars().all()
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

    payload = []
    for r in records:
        item = InspectionRecordResponse.model_validate(r).model_dump()
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
            record.updated_at = datetime.utcnow()
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

    task = await db.get(InspectionTask, record.task_id)
    if task:
        if current_user.role == "expert" and not await can_access_linked_task(db, task, current_user):
            raise HTTPException(status_code=403, detail="Not authorized")

    update_data = record_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(record, key, value)
    record.updated_at = datetime.utcnow()

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

    # 排除分类节点：仅统计挂了模板检查项且非分类的记录；无关联时仍计入兼容
    countable = []
    for r in records:
        if r.template_item is not None and getattr(r.template_item, "is_category", False):
            continue
        countable.append(r)

    total = len(countable)
    completed = sum(1 for r in countable if r.result)
    compliant = sum(1 for r in countable if _is_pass(r.result))
    non_compliant = sum(1 for r in countable if _is_fail(r.result))
    not_applicable = sum(1 for r in countable if _is_na(r.result))

    compliance_rate = (compliant / completed * 100) if completed > 0 else 0

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

    items_data = []
    for item in task_items:
        template_item = item.template_item
        # 分类节点不参与最终判定统计
        if template_item is not None and getattr(template_item, "is_category", False):
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
