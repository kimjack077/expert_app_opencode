"""
审核项目 API 路由
Audit Projects API Routes
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.services.report_generator import generate_audit_report_word, generate_audit_report_pdf
from app.models.audit_project import (
    AuditProject,
    AuditTeamMember,
    AuditPlanItem,
    AuditArea,
    AuditAreaRecord,
    Nonconformity,
    AuditReport,
    CommunicationMeeting,
)
from app.models.task import InspectionTask
from app.models.user import User
from app.models.enterprise import Enterprise
from app.schemas import ApiResponse
from app.schemas.audit_project import (
    AuditProjectCreate,
    AuditProjectUpdate,
    AuditProjectResponse,
    AuditTeamMemberCreate,
    AuditTeamMemberUpdate,
    AuditTeamMemberResponse,
    AuditPlanItemCreate,
    AuditPlanItemUpdate,
    AuditPlanItemResponse,
    AuditAreaCreate,
    AuditAreaUpdate,
    AuditAreaResponse,
    AuditAreaRecordCreate,
    AuditAreaRecordRequest,
    AuditAreaRecordUpdate,
    AuditAreaRecordResponse,
    NonconformityCreate,
    NonconformityRequest,
    NonconformityUpdate,
    NonconformityResponse,
    AuditReportCreate,
    AuditReportUpdate,
    AuditReportResponse,
    CommunicationMeetingCreate,
    CommunicationMeetingUpdate,
    CommunicationMeetingResponse,
)
from app.utils.security import get_current_user, get_user_from_token

router = APIRouter(prefix="/api/v1/audit-projects", tags=["audit-projects"])


def make_response(data=None, code=200, message="success"):
    """生成标准 API 响应格式，返回字典供 FastAPI 序列化"""
    # 使用 jsonable_encoder 将 SQLAlchemy 模型转换为可序列化的字典
    encoded_data = jsonable_encoder(data) if data is not None else None
    return {
        "code": code,
        "message": message,
        "data": encoded_data,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


# ==================== AuditProject Routes ====================

@router.post("")
async def create_audit_project(
    project: AuditProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建审核项目"""
    # 生成项目编号
    project_no = f"AUDIT-{datetime.now().strftime('%Y%m%d')}-{datetime.now().microsecond}"

    db_project = AuditProject(
        project_no=project_no,
        **project.model_dump(),
        created_by=current_user.id,
    )
    db.add(db_project)
    await db.commit()
    await db.refresh(db_project)
    return make_response(db_project)


@router.get("")
async def list_audit_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = None,
    enterprise_id: Optional[UUID] = None,
    audit_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取审核项目列表"""
    query = select(AuditProject)

    # 过滤条件
    conditions = []
    if status:
        conditions.append(AuditProject.status == status)
    if enterprise_id:
        conditions.append(AuditProject.enterprise_id == enterprise_id)
    if audit_type:
        conditions.append(AuditProject.audit_type == audit_type)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.offset(skip).limit(limit).order_by(AuditProject.created_at.desc())
    result = await db.execute(query)
    projects = result.scalars().all()
    return make_response(projects)


# ==================== My Tasks (审核员视角) ====================
# 注意：此路由必须在 /{project_id} 之前定义，否则会被误匹配

@router.get("/my-tasks")
async def get_my_audit_tasks(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取我的审核任务列表（审核员视角）"""
    # 查询分配给当前用户的审核计划项
    query = select(AuditPlanItem).where(
        AuditPlanItem.assigned_member_ids.contains([current_user.id])
    )

    if status:
        query = query.where(AuditPlanItem.status == status)

    query = query.order_by(AuditPlanItem.plan_date, AuditPlanItem.time_start)
    result = await db.execute(query)
    return make_response(result.scalars().all())


@router.get("/{project_id}")
async def get_audit_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取审核项目详情"""
    result = await db.execute(
        select(AuditProject).where(AuditProject.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="审核项目不存在")
    return make_response(project)


@router.put("/{project_id}")
async def update_audit_project(
    project_id: UUID,
    project_update: AuditProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新审核项目"""
    result = await db.execute(
        select(AuditProject).where(AuditProject.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="审核项目不存在")

    # 更新字段
    for field, value in project_update.model_dump(exclude_unset=True).items():
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project)
    return make_response(project)


@router.delete("/{project_id}")
async def delete_audit_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除审核项目"""
    result = await db.execute(
        select(AuditProject).where(AuditProject.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="审核项目不存在")

    await db.delete(project)
    await db.commit()
    return make_response(message="审核项目已删除")


# ==================== AuditTeamMember Routes ====================

@router.post("/{project_id}/team")
async def add_team_member(
    project_id: UUID,
    member: AuditTeamMemberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """添加审核组成员"""
    # 验证项目存在
    result = await db.execute(
        select(AuditProject).where(AuditProject.id == project_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="审核项目不存在")

    # 从用户表获取资质信息
    user_result = await db.execute(
        select(User).where(User.id == member.member_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    db_member = AuditTeamMember(
        project_id=project_id,
        **member.model_dump(exclude={"project_id", "registration_no", "registration_level"}),
        registration_no=user.auditor_registration_no,
        registration_level=user.auditor_level,
    )
    db.add(db_member)
    await db.commit()
    await db.refresh(db_member)
    return make_response(db_member)


@router.get("/{project_id}/team")
async def list_team_members(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取审核组成员列表"""
    result = await db.execute(
        select(AuditTeamMember)
        .where(AuditTeamMember.project_id == project_id)
        .order_by(AuditTeamMember.created_at)
    )
    members = result.scalars().all()
    
    member_ids = [m.member_id for m in members]
    if member_ids:
        users_result = await db.execute(
            select(User).where(User.id.in_(member_ids))
        )
        users = {u.id: u for u in users_result.scalars().all()}
    else:
        users = {}
    
    response_data = []
    for m in members:
        user = users.get(m.member_id)
        response_data.append({
            **AuditTeamMemberResponse.model_validate(m).model_dump(),
            "member_name": user.full_name if user else None,
            "member_username": user.username if user else None,
        })
    
    return make_response(response_data)


@router.put("/team/{member_id}")
async def update_team_member(
    member_id: UUID,
    member_update: AuditTeamMemberUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新审核组成员"""
    result = await db.execute(
        select(AuditTeamMember).where(AuditTeamMember.id == member_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="审核组成员不存在")

    for field, value in member_update.model_dump(exclude_unset=True).items():
        setattr(member, field, value)

    await db.commit()
    await db.refresh(member)
    return make_response(member)


@router.delete("/team/{member_id}")
async def remove_team_member(
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """移除审核组成员"""
    result = await db.execute(
        select(AuditTeamMember).where(AuditTeamMember.id == member_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="审核组成员不存在")

    await db.delete(member)
    await db.commit()
    return make_response(message="审核组成员已移除")


# ==================== AuditPlanItem Routes ====================

@router.post("/{project_id}/plan")
async def create_plan_item(
    project_id: UUID,
    plan_item: AuditPlanItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建审核计划项，同时自动创建检查任务下达给审核员"""
    project = await db.get(AuditProject, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="审核项目不存在")
    
    enterprise = await db.get(Enterprise, project.enterprise_id)
    
    import random
    random_suffix = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    task_no = f"TASK-{datetime.now().strftime('%Y%m%d')}-{random_suffix}"
    task_title = f"{project.title} - {plan_item.area_name} - {plan_item.plan_date}"
    
    assigned_to = plan_item.assigned_member_ids[0] if plan_item.assigned_member_ids else None
    
    inspection_task = InspectionTask(
        task_no=task_no,
        title=task_title,
        template_id=plan_item.template_id,
        assigned_to=assigned_to,
        assigned_by=current_user.id,
        target_name=enterprise.name if enterprise else project.title,
        target_address=enterprise.address if enterprise else None,
        scheduled_at=datetime.combine(plan_item.plan_date, datetime.min.time()),
        status="pending",
    )
    db.add(inspection_task)
    await db.flush()
    
    db_plan_item = AuditPlanItem(
        project_id=project_id,
        inspection_task_id=inspection_task.id,
        **plan_item.model_dump(exclude={"project_id"}),
    )
    db.add(db_plan_item)
    await db.commit()
    await db.refresh(db_plan_item)
    return make_response(db_plan_item)


@router.get("/{project_id}/plan")
async def list_plan_items(
    project_id: UUID,
    plan_date: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取审核计划项列表"""
    query = select(AuditPlanItem).where(AuditPlanItem.project_id == project_id)

    if plan_date:
        query = query.where(AuditPlanItem.plan_date == plan_date)
    if status:
        query = query.where(AuditPlanItem.status == status)

    query = query.order_by(AuditPlanItem.plan_date, AuditPlanItem.time_start)
    result = await db.execute(query)
    return make_response(result.scalars().all())


@router.get("/plan/{plan_item_id}")
async def get_plan_item(
    plan_item_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取审核计划项详情"""
    result = await db.execute(
        select(AuditPlanItem).where(AuditPlanItem.id == plan_item_id)
    )
    plan_item = result.scalar_one_or_none()
    if not plan_item:
        raise HTTPException(status_code=404, detail="审核计划项不存在")
    return make_response(plan_item)


@router.put("/plan/{plan_item_id}")
async def update_plan_item(
    plan_item_id: UUID,
    plan_item_update: AuditPlanItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新审核计划项"""
    result = await db.execute(
        select(AuditPlanItem).where(AuditPlanItem.id == plan_item_id)
    )
    plan_item = result.scalar_one_or_none()
    if not plan_item:
        raise HTTPException(status_code=404, detail="审核计划项不存在")

    for field, value in plan_item_update.model_dump(exclude_unset=True).items():
        setattr(plan_item, field, value)

    await db.commit()
    await db.refresh(plan_item)
    return make_response(plan_item)


@router.delete("/plan/{plan_item_id}")
async def delete_plan_item(
    plan_item_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除审核计划项"""
    result = await db.execute(
        select(AuditPlanItem).where(AuditPlanItem.id == plan_item_id)
    )
    plan_item = result.scalar_one_or_none()
    if not plan_item:
        raise HTTPException(status_code=404, detail="审核计划项不存在")

    await db.delete(plan_item)
    await db.commit()
    return make_response(message="审核计划项已删除")


# ==================== AuditAreaRecord Routes ====================

@router.post("/{project_id}/records")
async def create_area_record(
    project_id: UUID,
    record: AuditAreaRecordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建审核区域记录"""
    # 生成记录编号
    record_no = f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    db_record = AuditAreaRecord(
        project_id=project_id,
        record_no=record_no,
        recorded_by=current_user.id,
        **record.model_dump(),
    )
    db.add(db_record)
    await db.commit()
    await db.refresh(db_record)
    return make_response(db_record)


@router.get("/{project_id}/records")
async def list_area_records(
    project_id: UUID,
    area_id: Optional[UUID] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取审核区域记录列表"""
    query = select(AuditAreaRecord).where(AuditAreaRecord.project_id == project_id)

    if area_id:
        query = query.where(AuditAreaRecord.area_id == area_id)
    if status:
        query = query.where(AuditAreaRecord.status == status)

    query = query.order_by(AuditAreaRecord.created_at.desc())
    result = await db.execute(query)
    return make_response(result.scalars().all())


@router.get("/records/{record_id}")
async def get_area_record(
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取审核区域记录详情"""
    result = await db.execute(
        select(AuditAreaRecord).where(AuditAreaRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="审核区域记录不存在")
    return make_response(record)


@router.put("/records/{record_id}")
async def update_area_record(
    record_id: UUID,
    record_update: AuditAreaRecordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新审核区域记录"""
    result = await db.execute(
        select(AuditAreaRecord).where(AuditAreaRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="审核区域记录不存在")

    # 验证权限：只有主填写人或协作填写人可以更新
    if record.recorded_by != current_user.id and current_user.id not in record.co_recorders:
        raise HTTPException(status_code=403, detail="无权限更新此记录")

    for field, value in record_update.model_dump(exclude_unset=True).items():
        setattr(record, field, value)

    await db.commit()
    await db.refresh(record)
    return make_response(record)


# ==================== Nonconformity Routes ====================

@router.post("/{project_id}/nonconformities")
async def create_nonconformity(
    project_id: UUID,
    nc: NonconformityRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建不符合项"""
    # 生成不符合项编号
    nc_no = f"NC-{datetime.now().strftime('%Y%m%d')}-{datetime.now().microsecond}"

    db_nc = Nonconformity(
        project_id=project_id,
        nc_no=nc_no,
        created_by=current_user.id,
        **nc.model_dump(),
    )
    db.add(db_nc)
    await db.commit()
    await db.refresh(db_nc)
    return make_response(db_nc)


@router.get("/{project_id}/nonconformities")
async def list_nonconformities(
    project_id: UUID,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取不符合项列表"""
    query = select(Nonconformity).where(Nonconformity.project_id == project_id)

    if severity:
        query = query.where(Nonconformity.severity == severity)
    if status:
        query = query.where(Nonconformity.status == status)

    query = query.order_by(Nonconformity.created_at.desc())
    result = await db.execute(query)
    return make_response(result.scalars().all())


@router.put("/nonconformities/{nc_id}")
async def update_nonconformity(
    nc_id: UUID,
    nc_update: NonconformityUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新不符合项"""
    result = await db.execute(
        select(Nonconformity).where(Nonconformity.id == nc_id)
    )
    nc = result.scalar_one_or_none()
    if not nc:
        raise HTTPException(status_code=404, detail="不符合项不存在")

    for field, value in nc_update.model_dump(exclude_unset=True).items():
        setattr(nc, field, value)

    await db.commit()
    await db.refresh(nc)
    return make_response(nc)


# ==================== AuditReport Routes ====================

@router.post("/{project_id}/report")
async def create_audit_report(
    project_id: UUID,
    report: AuditReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建审核报告"""
    # 生成报告编号
    report_no = f"REP-{datetime.now().strftime('%Y%m%d')}-{datetime.now().microsecond}"

    db_report = AuditReport(
        project_id=project_id,
        report_no=report_no,
        prepared_by=current_user.id,
        **report.model_dump(exclude={"project_id"}),
    )
    db.add(db_report)
    await db.commit()
    await db.refresh(db_report)
    return make_response(db_report)


@router.get("/{project_id}/report")
async def list_audit_reports(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取审核报告列表"""
    result = await db.execute(
        select(AuditReport)
        .where(AuditReport.project_id == project_id)
        .order_by(AuditReport.created_at.desc())
    )
    return make_response(result.scalars().all())


@router.put("/report/{report_id}")
async def update_audit_report(
    report_id: UUID,
    report_update: AuditReportUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新审核报告"""
    result = await db.execute(
        select(AuditReport).where(AuditReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="审核报告不存在")

    for field, value in report_update.model_dump(exclude_unset=True).items():
        setattr(report, field, value)

    await db.commit()
    await db.refresh(report)
    return make_response(report)


# ==================== CommunicationMeeting Routes ====================

@router.post("/{project_id}/meetings")
async def create_meeting(
    project_id: UUID,
    meeting: CommunicationMeetingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建沟通会议记录"""
    db_meeting = CommunicationMeeting(
        project_id=project_id,
        created_by=current_user.id,
        **meeting.model_dump(exclude={"project_id"}),
    )
    db.add(db_meeting)
    await db.commit()
    await db.refresh(db_meeting)
    return make_response(db_meeting)


@router.get("/{project_id}/meetings")
async def list_meetings(
    project_id: UUID,
    meeting_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取沟通会议记录列表"""
    query = select(CommunicationMeeting).where(
        CommunicationMeeting.project_id == project_id
    )

    if meeting_type:
        query = query.where(CommunicationMeeting.meeting_type == meeting_type)

    query = query.order_by(CommunicationMeeting.meeting_time)
    result = await db.execute(query)
    return make_response(result.scalars().all())


@router.put("/meetings/{meeting_id}")
async def update_meeting(
    meeting_id: UUID,
    meeting_update: CommunicationMeetingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新沟通会议记录"""
    result = await db.execute(
        select(CommunicationMeeting).where(CommunicationMeeting.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="沟通会议记录不存在")

    for field, value in meeting_update.model_dump(exclude_unset=True).items():
        setattr(meeting, field, value)

    await db.commit()
    await db.refresh(meeting)
    return make_response(meeting)


# ==================== Progress Tracking ====================

@router.get("/{project_id}/progress")
async def get_project_progress(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取审核项目进度"""
    # 获取所有计划项
    plan_items_result = await db.execute(
        select(AuditPlanItem).where(AuditPlanItem.project_id == project_id)
    )
    plan_items = plan_items_result.scalars().all()

    # 统计各状态数量
    total = len(plan_items)
    pending = sum(1 for item in plan_items if item.status == "pending")
    in_progress = sum(1 for item in plan_items if item.status == "in_progress")
    completed = sum(1 for item in plan_items if item.status == "completed")

    # 获取不符合项统计
    nc_result = await db.execute(
        select(Nonconformity).where(Nonconformity.project_id == project_id)
    )
    nonconformities = nc_result.scalars().all()

    major_nc = sum(1 for nc in nonconformities if nc.severity == "major")
    minor_nc = sum(1 for nc in nonconformities if nc.severity == "minor")
    observations = sum(1 for nc in nonconformities if nc.severity == "observation")

    progress_data = {
        "project_id": str(project_id),
        "plan_items": {
            "total": total,
            "pending": pending,
            "in_progress": in_progress,
            "completed": completed,
            "completion_rate": round(completed / total * 100, 2) if total > 0 else 0,
        },
        "nonconformities": {
            "total": len(nonconformities),
            "major": major_nc,
            "minor": minor_nc,
            "observations": observations,
        },
    }
    return make_response(progress_data)


# ==================== Report Export ====================

@router.get("/{project_id}/export/word")
async def export_report_word(
    project_id: UUID,
    token: str = Query(..., description="认证令牌"),
    db: AsyncSession = Depends(get_db),
):
    """导出 Word 格式审核报告"""
    # Authenticate using token query parameter
    current_user = await get_user_from_token(token, db)

    try:
        buffer = await generate_audit_report_word(db, project_id)

        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename=audit_report_{project_id}.docx"
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成报告失败: {str(e)}")


@router.get("/{project_id}/export/pdf")
async def export_report_pdf(
    project_id: UUID,
    token: str = Query(..., description="认证令牌"),
    db: AsyncSession = Depends(get_db),
):
    """导出 PDF 格式审核报告"""
    # Authenticate using token query parameter
    current_user = await get_user_from_token(token, db)

    try:
        buffer = await generate_audit_report_pdf(db, project_id)

        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=audit_report_{project_id}.pdf"
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成报告失败: {str(e)}")


# ==================== AI Agent ====================

from app.services.audit_agent import (
    prepare_audit_with_ai,
    evaluate_evidence_with_ai,
    generate_report_with_ai,
    suggest_nc_with_ai,
)

@router.post("/{project_id}/ai/prepare")
async def ai_prepare_audit(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 审核准备建议"""
    try:
        result = await prepare_audit_with_ai(db, project_id)
        return {"code": 200, "message": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 服务失败: {str(e)}")


@router.post("/{project_id}/ai/evaluate-evidence")
async def ai_evaluate_evidence(
    project_id: UUID,
    evidence: str,
    clause_no: str,
    certification_system: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 证据充分性评估"""
    try:
        result = await evaluate_evidence_with_ai(db, evidence, clause_no, certification_system)
        return {"code": 200, "message": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 服务失败: {str(e)}")


@router.post("/{project_id}/ai/generate-report")
async def ai_generate_report(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 生成审核报告叙述性评价"""
    try:
        result = await generate_report_with_ai(db, project_id)
        return {"code": 200, "message": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 服务失败: {str(e)}")


@router.post("/{project_id}/ai/suggest-nc")
async def ai_suggest_nonconformity(
    project_id: UUID,
    evidence: str,
    clause_no: str,
    certification_system: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 建议不符合项"""
    try:
        result = await suggest_nc_with_ai(db, evidence, clause_no, certification_system)
        return {"code": 200, "message": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 服务失败: {str(e)}")
