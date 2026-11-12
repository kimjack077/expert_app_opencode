from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.media import MediaFile
from app.models.task import InspectionTask, TaskItemRecord
from app.models.record import InspectionRecord, InspectionRecordItem
from app.models.audit_project import AuditAreaRecord, AuditPlanItem
from app.models.user import User
from app.schemas import ApiResponse, MediaFileResponse
from app.utils.security import get_current_user
from app.utils.file_handler import save_upload_file
from app.services import AuditService
from app.services.formal_audit_sync_service import can_access_linked_task
from app.utils.response import make_response
from app.utils.roles import is_admin, REVIEWER_ROLES
from app.services.project_access_service import ensure_project_access

router = APIRouter()




@router.post("/upload", response_model=ApiResponse)
async def upload_file(
    file: UploadFile = File(...),
    task_id: str = Form(None),
    record_id: str = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    valid_record_id = None
    linked_task_id = None
    if current_user.role in REVIEWER_ROLES:
        raise HTTPException(status_code=403, detail="只读审核员不能上传附件")
    if record_id:
        task_item = await db.get(TaskItemRecord, record_id)
        if task_item:
            valid_record_id = str(task_item.id)
            linked_task_id = task_item.task_id
        else:
            # media_files.record_id 只引用任务明细；正式明细须经区域记录、计划项桥接。
            # 独立记录没有任务时不猜测归属，仍由调用方将上传 URL 写入 photos。
            rec_item = await db.get(InspectionRecordItem, record_id)
            if rec_item:
                if rec_item.record_id:
                    inspection = await db.get(InspectionRecord, rec_item.record_id)
                    if not inspection or inspection.is_deleted:
                        raise HTTPException(status_code=404, detail="Record not found")
                    if not is_admin(current_user.role) and str(inspection.inspector_id) != str(current_user.id):
                        raise HTTPException(status_code=403, detail="没有权限修改该检查记录")
                    if inspection.status == "submitted":
                        raise HTTPException(status_code=409, detail="该检查记录已提交，不可上传附件")
                if rec_item.audit_area_record_id:
                    area_record = await db.get(
                        AuditAreaRecord, rec_item.audit_area_record_id
                    )
                    if not area_record:
                        raise HTTPException(status_code=404, detail="审核区域记录不存在")
                    await ensure_project_access(db, area_record.project_id, current_user)
                    if str(area_record.recorded_by) != str(current_user.id) and str(current_user.id) not in {
                        str(user_id) for user_id in area_record.co_recorders or []
                    }:
                        raise HTTPException(status_code=403, detail="无权限更新此记录")
                    if area_record.status == "submitted":
                        raise HTTPException(status_code=409, detail="该审核记录已提交，不可上传附件")
                    if area_record and area_record.plan_item_id:
                        plan_item = await db.get(AuditPlanItem, area_record.plan_item_id)
                        if plan_item:
                            linked_task_id = plan_item.inspection_task_id
                # 即使显式传了任务，也必须检查正式记录的真实归属，不能用它绕过桥接。
                if task_id and linked_task_id and str(task_id) != str(linked_task_id):
                    raise HTTPException(status_code=400, detail="Task and record do not match")
                matched_task_id = linked_task_id or task_id
                if matched_task_id and rec_item.template_item_id:
                    matched = (
                        await db.execute(
                            select(TaskItemRecord).where(
                                TaskItemRecord.task_id == matched_task_id,
                                TaskItemRecord.template_item_id == rec_item.template_item_id,
                            )
                        )
                    ).scalar_one_or_none()
                    if matched:
                        valid_record_id = str(matched.id)
                        linked_task_id = matched.task_id
                if not rec_item.record_id and not rec_item.audit_area_record_id:
                    raise HTTPException(status_code=404, detail="检查项缺少所属记录")
            else:
                raise HTTPException(status_code=404, detail="Record item not found")

    if task_id and linked_task_id and str(task_id) != str(linked_task_id):
        raise HTTPException(status_code=400, detail="Task and record do not match")
    task_id = str(linked_task_id) if linked_task_id else task_id
    if task_id:
        task = await db.get(InspectionTask, task_id)
        if not task or task.is_deleted:
            raise HTTPException(status_code=404, detail="Task not found")
        # 所有入口在最终任务解析后鉴权，复用多人分派规则，不因仅传 record_id 绕过。
        if not await can_access_linked_task(db, task, current_user):
            raise HTTPException(status_code=403, detail="Not authorized")
        if task.status in {"completed", "cancelled"}:
            raise HTTPException(status_code=409, detail="该任务已结束，不可上传附件")

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
    if task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    if not await can_access_linked_task(db, task, current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

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
