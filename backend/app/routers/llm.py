from datetime import datetime
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

router = APIRouter()


def make_response(data=None, code=200, message="success"):
    return ApiResponse(
        code=code, message=message, data=data, timestamp=datetime.utcnow()
    )


@router.post("/suggestion", response_model=ApiResponse)
async def get_suggestion(
    request: LLMRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not request.record_id:
        raise HTTPException(status_code=400, detail="record_id is required")

    result = await db.execute(
        select(InspectionRecordItem)
        .options(selectinload(InspectionRecordItem.template_item))
        .where(InspectionRecordItem.id == request.record_id)
    )
    record_item = result.scalar_one_or_none()
    if not record_item:
        raise HTTPException(status_code=404, detail="Record item not found")

    if not record_item.template_item:
        raise HTTPException(status_code=400, detail="Template item not found")

    suggestion, from_cache, duration_ms = await llm_service.get_suggestion(
        template_item=record_item.template_item,
        record=record_item,
        db=db,
        user_id=str(current_user.id),
        task_id=request.task_id or str(record_item.record_id),
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

    result = await db.execute(
        select(InspectionRecordItem)
        .options(selectinload(InspectionRecordItem.template_item))
        .where(InspectionRecordItem.id == request.record_id)
    )
    record_item = result.scalar_one_or_none()
    if not record_item:
        raise HTTPException(status_code=404, detail="Record item not found")

    if not record_item.template_item:
        raise HTTPException(status_code=400, detail="Template item not found")

    basis, from_cache, duration_ms = await llm_service.get_basis(
        template_item=record_item.template_item,
        record=record_item,
        db=db,
        user_id=str(current_user.id),
        task_id=request.task_id or str(record_item.record_id),
        use_cache=request.use_cache,
    )

    await db.commit()

    return make_response(data={
        "content": basis,
        "from_cache": from_cache,
        "duration_ms": duration_ms,
    })
