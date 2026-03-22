from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.task import InspectionTask, TaskItemRecord
from app.models.template import TemplateItem
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
    query = select(InspectionTask)

    if current_user.role == "expert":
        query = query.where(InspectionTask.assigned_to == current_user.id)

    if status:
        query = query.where(InspectionTask.status == status)

    query = query.order_by(InspectionTask.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    tasks = result.scalars().all()

    total = (await db.execute(select(func.count(InspectionTask.id)))).scalar()

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
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if current_user.role == "expert" and str(task.assigned_to) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to view this task")

    return make_response(data=InspectionTaskResponse.model_validate(task).model_dump())


@router.put("/{task_id}", response_model=ApiResponse)
async def update_task(
    task_id: str,
    task_data: InspectionTaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(InspectionTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 专家用户只能更新分配给自己的任务状态
    if current_user.role == "expert":
        if str(task.assigned_to) != str(current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized to update this task")
        # 专家用户只能更新状态
        if task_data.status:
            task.status = task_data.status
            if task_data.status == "in_progress":
                task.started_at = datetime.utcnow()
            elif task_data.status == "completed":
                task.completed_at = datetime.utcnow()
    else:
        # 管理员可以更新所有字段
        update_data = task_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(task, key, value)

    await db.commit()
    await db.refresh(task)

    return make_response(data=InspectionTaskResponse.model_validate(task).model_dump())


@router.post("/{task_id}/start", response_model=ApiResponse)
async def start_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(InspectionTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 管理员可以启动任何任务，专家只能启动分配给自己的任务
    if current_user.role == "expert" and str(task.assigned_to) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not assigned to you")

    if task.status != "pending":
        raise HTTPException(status_code=400, detail="Task cannot be started")

    task.status = "in_progress"
    task.started_at = datetime.utcnow()
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
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 管理员可以完成任何任务，专家只能完成分配给自己的任务
    if current_user.role == "expert" and str(task.assigned_to) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not assigned to you")

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


@router.get("/{task_id}/records", response_model=ApiResponse)
async def get_task_records(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(InspectionTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if current_user.role == "expert" and str(task.assigned_to) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(InspectionRecord)
        .options(selectinload(InspectionRecord.template_item))
        .where(InspectionRecord.task_id == task_id)
        .order_by(InspectionRecord.recorded_at)
    )
    records = result.scalars().all()

    return make_response(
        data=[InspectionRecordResponse.model_validate(r).model_dump() for r in records]
    )


@router.post("/{task_id}/records", response_model=ApiResponse)
async def create_or_update_record(
    task_id: str,
    record_data: InspectionRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(InspectionTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 管理员可以为任何任务创建记录，专家只能为分配给自己的任务创建记录
    if current_user.role == "expert" and str(task.assigned_to) != str(current_user.id):
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
        if current_user.role == "expert" and str(task.assigned_to) != str(current_user.id):
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
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    result = await db.execute(
        select(InspectionRecord).where(InspectionRecord.task_id == task_id)
    )
    records = result.scalars().all()

    total = len(records)
    completed = sum(1 for r in records if r.result)
    compliant = sum(1 for r in records if r.result == "compliant")
    non_compliant = sum(1 for r in records if r.result == "non_compliant")
    not_applicable = sum(1 for r in records if r.result == "not_applicable")

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
