from typing import Union
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.task import TaskItemRecord
from app.models.record import InspectionRecord, InspectionRecordItem
from app.models.template import TemplateItem
from app.schemas import ApiResponse, LLMRequest, LLMResponse
from app.utils.security import get_current_user
from app.services import llm_service, AuditService
from app.utils.response import make_response

router = APIRouter()




async def get_record_and_template(
    record_id: str,
    db: AsyncSession
) -> tuple[Union[TaskItemRecord, InspectionRecordItem, None], TemplateItem | None]:
    """
    根据record_id查找记录和对应的模板项
    支持 TaskItemRecord 和 InspectionRecordItem 两种类型
    """
    # 先尝试 TaskItemRecord
    result = await db.execute(
        select(TaskItemRecord)
        .options(selectinload(TaskItemRecord.template_item))
        .where(TaskItemRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if record and record.template_item:
        return record, record.template_item

    # 再尝试 InspectionRecordItem
    result = await db.execute(
        select(InspectionRecordItem)
        .options(selectinload(InspectionRecordItem.template_item))
        .where(InspectionRecordItem.id == record_id)
    )
    record = result.scalar_one_or_none()
    if record and record.template_item:
        return record, record.template_item

    return None, None


@router.post("/suggestion", response_model=ApiResponse)
async def get_suggestion(
    request: LLMRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not request.record_id:
        raise HTTPException(status_code=400, detail="record_id is required")

    record_item, template_item = await get_record_and_template(str(request.record_id), db)

    if not record_item:
        raise HTTPException(status_code=404, detail="Record item not found")

    if not template_item:
        raise HTTPException(status_code=400, detail="Template item not found")

    suggestion, from_cache, duration_ms = await llm_service.get_suggestion(
        template_item=template_item,
        record=record_item,
        db=db,
        user_id=str(current_user.id),
        task_id=str(request.task_id),
        use_cache=request.use_cache,
    )

    await db.commit()

    return make_response(data={
        "content": suggestion,
        "from_cache": from_cache,
        "duration_ms": duration_ms,
    })


@router.post("/basis", response_model=ApiResponse)
async def get_basis(
    request: LLMRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not request.record_id:
        raise HTTPException(status_code=400, detail="record_id is required")

    record_item, template_item = await get_record_and_template(str(request.record_id), db)

    if not record_item:
        raise HTTPException(status_code=404, detail="Record item not found")

    if not template_item:
        raise HTTPException(status_code=400, detail="Template item not found")

    basis, from_cache, duration_ms = await llm_service.get_basis(
        template_item=template_item,
        record=record_item,
        db=db,
        user_id=str(current_user.id),
        task_id=str(request.task_id),
        use_cache=request.use_cache,
    )

    await db.commit()

    return make_response(data={
        "content": basis,
        "from_cache": from_cache,
        "duration_ms": duration_ms,
    })