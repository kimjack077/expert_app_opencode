from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.media import MediaFile
from app.models.task import InspectionTask, TaskItemRecord
from app.models.record import InspectionRecord, InspectionRecordItem
from app.models.user import User
from app.schemas import ApiResponse, MediaFileResponse
from app.utils.security import get_current_user
from app.utils.file_handler import save_upload_file
from app.services import AuditService

router = APIRouter()


def make_response(data=None, code=200, message="success"):
    return ApiResponse(
        code=code, message=message, data=data, timestamp=datetime.now(timezone.utc)
    )


@router.post("/upload", response_model=ApiResponse)
async def upload_file(
    file: UploadFile = File(...),
    task_id: str = Form(None),
    record_id: str = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if task_id:
        task = await db.get(InspectionTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # 允许任务分配人、管理员上传
        is_assignee = str(task.assigned_to) == str(current_user.id)
        is_admin = current_user.role in ("super_admin", "admin")
        if not is_assignee and not is_admin:
            raise HTTPException(status_code=403, detail="Not authorized")

    valid_record_id = None
    if record_id:
        try:
            task_item = await db.get(TaskItemRecord, record_id)
            if task_item:
                valid_record_id = record_id
            else:
                # 记录流上传时前端可能传的是 InspectionRecordItem 的 ID；
                # media_files.record_id 外键指向 task_item_records，
                # 因此需换算成同一任务、同一模板项对应的 TaskItemRecord ID，才能保住关联。
                rec_item = await db.get(InspectionRecordItem, record_id)
                if rec_item and rec_item.template_item_id:
                    parent = (
                        await db.get(InspectionRecord, rec_item.record_id)
                        if rec_item.record_id
                        else None
                    )
                    if parent and parent.task_id:
                        matched = (
                            await db.execute(
                                select(TaskItemRecord).where(
                                    TaskItemRecord.task_id == parent.task_id,
                                    TaskItemRecord.template_item_id
                                    == rec_item.template_item_id,
                                )
                            )
                        ).scalar_one_or_none()
                        if matched:
                            valid_record_id = str(matched.id)
        except Exception:
            valid_record_id = None

    stored_name, file_path, file_size = await save_upload_file(file, "inspections")

    media = MediaFile(
        task_id=task_id,
        record_id=valid_record_id,
        file_type="image"
        if file.content_type and file.content_type.startswith("image/")
        else "document",
        original_name=file.filename,
        stored_name=stored_name,
        file_path=file_path,
        file_size=file_size,
        mime_type=file.content_type,
        uploaded_by=current_user.id,
    )
    db.add(media)
    await db.commit()
    await db.refresh(media)

    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "upload_file",
        "media",
        str(media.id),
    )

    return make_response(data=MediaFileResponse.model_validate(media).model_dump())


@router.get("/task/{task_id}", response_model=ApiResponse)
async def get_task_media(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await db.get(InspectionTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    result = await db.execute(
        select(MediaFile)
        .where(
            MediaFile.task_id == task_id,
            MediaFile.is_deleted == False,  # noqa: E712
        )
        .order_by(MediaFile.uploaded_at.desc())
    )
    files = result.scalars().all()

    return make_response(
        data=[MediaFileResponse.model_validate(f).model_dump() for f in files]
    )


@router.delete("/{media_id}", response_model=ApiResponse)
async def delete_media(
    media_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除媒体文件（软删除）"""
    media = await db.get(MediaFile, media_id)
    if not media or media.is_deleted:
        raise HTTPException(status_code=404, detail="Media not found")

    if str(media.uploaded_by) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    from app.utils.soft_delete import soft_delete

    await soft_delete(db, media)
    await db.commit()

    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "delete_file",
        "media",
        media_id,
    )

    return make_response(message="Media deleted")
