"""
审核项目 API 路由
Audit Projects API Routes
"""
import json
from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.services.project_access_service import (
    ensure_project_access,
    project_visibility_condition,
)
from app.utils.response import utc_now_iso
from app.utils.category import is_category_node, load_parent_ids
from app.services.project_artifact_service import project_artifact_service
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
from app.models.task import InspectionTask, TaskItemRecord
from app.models.template import TemplateItem
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

router = APIRouter(prefix="/api/audit-projects", tags=["audit-projects"])


def make_response(data=None, code=200, message="success"):
    """生成标准 API 响应格式，返回字典供 FastAPI 序列化"""
    # 使用 jsonable_encoder 将 SQLAlchemy 模型转换为可序列化的字典
    encoded_data = jsonable_encoder(data) if data is not None else None
    return {
        "code": code,
        "message": message,
        "data": encoded_data,
        # 统一时间戳格式；注意不能再手工拼 "Z"：
        # 现在的时间已带 +00:00 偏移，再加 Z 会产出非法的 ISO8601。
        "timestamp": utc_now_iso()
    }


def area_record_response(record: AuditAreaRecord) -> dict:
    """Expose the formal area name without making clients infer it from IDs."""
    value = jsonable_encoder(record)
    value["area_name"] = (
        record.area.area_name
        if record.area
        else record.plan_item.area_name
        if record.plan_item
        else None
    )
    if not value.get("template_id") and record.plan_item and record.plan_item.template_id:
        value["template_id"] = str(record.plan_item.template_id)
    if record.plan_item:
        value["plan_item"] = {
            "id": str(record.plan_item.id),
            "area_name": record.plan_item.area_name,
            "plan_date": str(record.plan_item.plan_date) if record.plan_item.plan_date else None,
            "time_start": record.plan_item.time_start,
            "time_end": record.plan_item.time_end,
            "group_no": record.plan_item.group_no,
            "status": record.plan_item.status,
        }
    items = record.items or []
    value["items_count"] = len(items)
    value["pass_count"] = sum(1 for i in items if i.result == "pass" or i.evaluation_3level in {"1", "2"})
    value["fail_count"] = sum(1 for i in items if i.result == "fail" or i.evaluation_3level == "3")
    return value


def _task_progress_fields(
    plan_item: AuditPlanItem,
    record: AuditAreaRecord | None = None,
    nonconformities: list[Nonconformity] | None = None,
    template_item_count: int = 0,
) -> dict[str, Any]:
    """Build auditor-facing progress from the latest formal area record."""

    clause_keys: set[str] = set()
    for raw_clause in plan_item.clauses or []:
        if isinstance(raw_clause, dict):
            raw_clause = raw_clause.get("clause_no") or raw_clause.get("clause") or raw_clause.get("id")
        clause = str(raw_clause or "").strip()
        if clause:
            clause_keys.add(clause)
    total_clause_count = int(template_item_count or 0) or len(clause_keys)

    record_items = list(getattr(record, "items", None) or [])
    confirmed_record_count = len(record_items)
    completion_rate = (
        round(min(100, confirmed_record_count / total_clause_count * 100), 2)
        if total_clause_count
        else (100.0 if getattr(plan_item, "status", "") == "completed" else 0.0)
    )

    formal_ncs = [
        nc for nc in (nonconformities or [])
        if str(getattr(nc, "status", "") or "") != "rejected"
    ]
    unresolved_ncs = [
        nc for nc in formal_ncs
        if str(getattr(nc, "status", "") or "") != "closed"
    ]
    record_exceptions = sum(
        1 for item in record_items
        if str(getattr(item, "evaluation_3level", "") or "") == "3"
    )
    return {
        "total_clause_count": total_clause_count,
        "confirmed_record_count": confirmed_record_count,
        "completion_rate": completion_rate,
        "exception_count": max(len(unresolved_ncs), record_exceptions),
        "has_nc": bool(formal_ncs),
        "record_status": getattr(record, "status", None) if record else None,
    }


def _validate_nonconformity_transition(
    nc: Nonconformity,
    update_data: dict[str, Any],
) -> None:
    next_status = str(update_data.get("status", nc.status) or "")
    corrective_action = update_data.get("corrective_action", nc.corrective_action)
    verification_result = update_data.get("verification_result", nc.verification_result)

    if next_status in {"corrected", "pending_verification", "verified", "closed"}:
        if not str(corrective_action or "").strip():
            raise HTTPException(
                status_code=422,
                detail="不符合项进入已整改或后续状态前必须填写整改措施",
            )
    if next_status in {"verified", "closed"}:
        if not str(verification_result or "").strip():
            raise HTTPException(
                status_code=422,
                detail="不符合项验证或关闭前必须填写验证结果",
            )


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
    keyword: Optional[str] = Query(None, description="项目编号 / 项目名称模糊搜索"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取审核项目列表

    返回 ``{"items": [...], "total": n}``。
    原先返回纯数组且不带 total，前端只能把「当页条数」当成总数，分页器数字是错的。
    筛选条件只构建一次，分页查询与计数查询共用，避免两边漂移。
    """
    conditions = [AuditProject.is_deleted == False]  # noqa: E712

    # 可见性：非平台管理角色只能看到自己创建/负责/参与的项目。
    # 缺少此过滤会导致任何登录用户都能枚举全部项目元数据。
    visibility = project_visibility_condition(current_user)
    if visibility is not None:
        conditions.append(visibility)

    # 过滤条件
    if status:
        conditions.append(AuditProject.status == status)
    if enterprise_id:
        conditions.append(AuditProject.enterprise_id == enterprise_id)
    if audit_type:
        conditions.append(AuditProject.audit_type == audit_type)
    if keyword and keyword.strip():
        like = f"%{keyword.strip()}%"
        conditions.append(
            or_(
                AuditProject.project_no.ilike(like),
                AuditProject.title.ilike(like),
            )
        )

    total = (
        await db.execute(select(func.count(AuditProject.id)).where(and_(*conditions)))
    ).scalar() or 0

    query = (
        select(AuditProject)
        .where(and_(*conditions))
        .order_by(AuditProject.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    projects = result.scalars().all()

    return make_response(
        {"items": jsonable_encoder(projects), "total": total}
    )


# ==================== My Tasks (审核员视角) ====================
# 注意：此路由必须在 /{project_id} 之前定义，否则会被误匹配

@router.get("/my-tasks")
async def get_my_audit_tasks(
    status: Optional[str] = None,
    today_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取我的审核任务列表（审核员视角）

    默认返回全部分配给当前用户的计划项；传 today_only=true 仅返回今日任务。
    响应补充 project_title / enterprise_name / inspection_task_id，供 Web「我的审核任务」展示。
    """
    query = select(AuditPlanItem).where(
        AuditPlanItem.assigned_member_ids.contains([current_user.id]),
        AuditPlanItem.is_deleted == False,  # noqa: E712
    )

    if status:
        query = query.where(AuditPlanItem.status == status)

    if today_only:
        from datetime import date
        today = date.today()
        query = query.where(AuditPlanItem.plan_date == today)

    query = query.order_by(AuditPlanItem.plan_date.desc(), AuditPlanItem.time_start)
    result = await db.execute(query)
    plan_items = result.scalars().all()

    # 批量加载项目与企业，避免 N+1
    project_ids = {item.project_id for item in plan_items if item.project_id}
    projects_by_id = {}
    enterprises_by_id = {}
    if project_ids:
        projects = (
            await db.execute(select(AuditProject).where(AuditProject.id.in_(project_ids)))
        ).scalars().all()
        projects_by_id = {p.id: p for p in projects}
        enterprise_ids = {p.enterprise_id for p in projects if p.enterprise_id}
        if enterprise_ids:
            enterprises = (
                await db.execute(select(Enterprise).where(Enterprise.id.in_(enterprise_ids)))
            ).scalars().all()
            enterprises_by_id = {e.id: e for e in enterprises}

    plan_item_ids = {item.id for item in plan_items}
    latest_records_by_plan: dict[UUID, AuditAreaRecord] = {}
    nonconformities_by_plan: dict[UUID, list[Nonconformity]] = {}
    template_item_counts: dict[UUID, int] = {}
    if plan_item_ids:
        records = (
            await db.execute(
                select(AuditAreaRecord)
                .where(AuditAreaRecord.plan_item_id.in_(plan_item_ids))
                .options(selectinload(AuditAreaRecord.items))
                .order_by(AuditAreaRecord.created_at.desc())
            )
        ).scalars().unique().all()
        for record in records:
            if record.plan_item_id:
                latest_records_by_plan.setdefault(record.plan_item_id, record)

        nonconformities = (
            await db.execute(
                select(Nonconformity).where(Nonconformity.plan_item_id.in_(plan_item_ids))
            )
        ).scalars().all()
        for nc in nonconformities:
            if nc.plan_item_id:
                nonconformities_by_plan.setdefault(nc.plan_item_id, []).append(nc)

        template_ids = {item.template_id for item in plan_items if item.template_id}
        if template_ids:
            parent_ids = await load_parent_ids(db, template_ids=template_ids)
            template_items = (
                await db.execute(
                    select(TemplateItem).where(
                        TemplateItem.template_id.in_(template_ids),
                        TemplateItem.is_deleted == False,  # noqa: E712
                        TemplateItem.is_category.is_not(True),
                    )
                )
            ).scalars().all()
            for template_item in template_items:
                # 检查项数量 = 真正的叶子检查项数，分类目录不计入
                if is_category_node(template_item, parent_ids):
                    continue
                template_item_counts[template_item.template_id] = (
                    template_item_counts.get(template_item.template_id, 0) + 1
                )

    payload = []
    for item in plan_items:
        project = projects_by_id.get(item.project_id)
        enterprise = (
            enterprises_by_id.get(project.enterprise_id)
            if project and project.enterprise_id
            else None
        )
        row = jsonable_encoder(item)
        row.update(
            {
                "project_id": str(item.project_id) if item.project_id else None,
                "project_no": project.project_no if project else None,
                "project_title": project.title if project else None,
                "enterprise_name": enterprise.name if enterprise else None,
                "inspection_task_id": (
                    str(item.inspection_task_id) if item.inspection_task_id else None
                ),
                **_task_progress_fields(
                    item,
                    latest_records_by_plan.get(item.id),
                    nonconformities_by_plan.get(item.id, []),
                    template_item_counts.get(item.template_id, 0) if item.template_id else 0,
                ),
            }
        )
        payload.append(row)

    return make_response(payload)


@router.get("/{project_id}")
async def get_audit_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取审核项目详情"""
    await ensure_project_access(db, project_id, current_user)
    result = await db.execute(
        select(AuditProject).where(
            AuditProject.id == project_id,
            AuditProject.is_deleted == False,  # noqa: E712
        )
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
    await ensure_project_access(db, project_id, current_user, require_manage=True)
    result = await db.execute(
        select(AuditProject).where(
            AuditProject.id == project_id,
            AuditProject.is_deleted == False,  # noqa: E712
        )
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
    """删除审核项目（软删除）"""
    await ensure_project_access(db, project_id, current_user, require_manage=True)
    result = await db.execute(
        select(AuditProject).where(AuditProject.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project or project.is_deleted:
        raise HTTPException(status_code=404, detail="审核项目不存在")

    from app.utils.soft_delete import soft_delete

    # 软删除项目本身（project_no 唯一字段需追加后缀避免冲突）
    await soft_delete(db, project, unique_fields=["project_no"])
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
    await ensure_project_access(db, project_id, current_user, require_manage=True)
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

    # 去重：同一成员在未删除记录中只能加入一次（BUG-14）
    dup = await db.execute(
        select(AuditTeamMember.id)
        .where(
            AuditTeamMember.project_id == project_id,
            AuditTeamMember.member_id == member.member_id,
            AuditTeamMember.is_deleted == False,  # noqa: E712
        )
        .limit(1)
    )
    if dup.scalars().first() is not None:
        raise HTTPException(status_code=409, detail="该成员已在审核组中，请勿重复添加")

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
    await ensure_project_access(db, project_id, current_user)
    result = await db.execute(
        select(AuditTeamMember)
        .where(
            AuditTeamMember.project_id == project_id,
            AuditTeamMember.is_deleted == False,  # noqa: E712
        )
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
        select(AuditTeamMember).where(
            AuditTeamMember.id == member_id,
            AuditTeamMember.is_deleted == False,  # noqa: E712
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="审核组成员不存在")
    await ensure_project_access(db, member.project_id, current_user, require_manage=True)

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
    """移除审核组成员（软删除）"""
    result = await db.execute(
        select(AuditTeamMember).where(
            AuditTeamMember.id == member_id,
            AuditTeamMember.is_deleted == False,  # noqa: E712
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="审核组成员不存在")
    await ensure_project_access(db, member.project_id, current_user, require_manage=True)

    from app.utils.soft_delete import soft_delete

    await soft_delete(db, member)
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
    await ensure_project_access(db, project_id, current_user, require_manage=True)
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
    
    if plan_item.template_id:
        # 分类目录集合统一走 app/utils/category
        parent_ids = await load_parent_ids(db, template_id=plan_item.template_id)

        items_result = await db.execute(
            select(TemplateItem)
            .where(
                TemplateItem.template_id == plan_item.template_id,
                TemplateItem.is_deleted == False,  # noqa: E712
                TemplateItem.is_category.is_not(True),
            )
            .order_by(TemplateItem.sort_order)
        )
        leaf_items = [
            i for i in items_result.scalars().all()
            if not is_category_node(i, parent_ids)
        ]

        for item in leaf_items:
            record = TaskItemRecord(
                task_id=inspection_task.id,
                template_item_id=item.id,
            )
            db.add(record)
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
    await ensure_project_access(db, project_id, current_user)
    query = select(AuditPlanItem).where(
        AuditPlanItem.project_id == project_id,
        AuditPlanItem.is_deleted == False,  # noqa: E712
    )

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
        select(AuditPlanItem).where(
            AuditPlanItem.id == plan_item_id,
            AuditPlanItem.is_deleted == False,  # noqa: E712
        )
    )
    plan_item = result.scalar_one_or_none()
    if not plan_item:
        raise HTTPException(status_code=404, detail="审核计划项不存在")
    await ensure_project_access(db, plan_item.project_id, current_user)
    return make_response(plan_item)


@router.put("/plan/{plan_item_id}")
async def update_plan_item(
    plan_item_id: UUID,
    plan_item_update: AuditPlanItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新审核计划项，同时同步更新关联的检查任务"""
    result = await db.execute(
        select(AuditPlanItem).where(
            AuditPlanItem.id == plan_item_id,
            AuditPlanItem.is_deleted == False,  # noqa: E712
        )
    )
    plan_item = result.scalar_one_or_none()
    if not plan_item:
        raise HTTPException(status_code=404, detail="审核计划项不存在")
    await ensure_project_access(db, plan_item.project_id, current_user, require_manage=True)

    # 更新审核计划项字段
    for field, value in plan_item_update.model_dump(exclude_unset=True).items():
        setattr(plan_item, field, value)

    # 同步更新关联的检查任务
    if plan_item.inspection_task_id:
        inspection_task = await db.get(InspectionTask, plan_item.inspection_task_id)
        if inspection_task:
            # 获取项目和企业信息
            project = await db.get(AuditProject, plan_item.project_id)
            enterprise = None
            if project:
                enterprise = await db.get(Enterprise, project.enterprise_id)

            # 更新检查任务标题（包含区域信息）
            if project and plan_item.area_name:
                inspection_task.title = f"{project.title} - {plan_item.area_name} - {plan_item.plan_date}"

            # 更新检查任务分配人
            if plan_item.assigned_member_ids and len(plan_item.assigned_member_ids) > 0:
                inspection_task.assigned_to = plan_item.assigned_member_ids[0]

            # 更新检查任务模板
            if plan_item.template_id:
                inspection_task.template_id = plan_item.template_id

            # 更新检查任务时间
            if plan_item.plan_date:
                inspection_task.scheduled_at = datetime.combine(plan_item.plan_date, datetime.min.time())

            # 确保 target_name 和 target_address 始终是企业信息
            if enterprise:
                inspection_task.target_name = enterprise.name
                inspection_task.target_address = enterprise.address
            elif project:
                inspection_task.target_name = project.title

    await db.commit()
    await db.refresh(plan_item)
    return make_response(plan_item)


@router.delete("/plan/{plan_item_id}")
async def delete_plan_item(
    plan_item_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除审核计划项（软删除），同时软删除关联的检查任务"""
    result = await db.execute(
        select(AuditPlanItem).where(
            AuditPlanItem.id == plan_item_id,
            AuditPlanItem.is_deleted == False,  # noqa: E712
        )
    )
    plan_item = result.scalar_one_or_none()
    if not plan_item:
        raise HTTPException(status_code=404, detail="审核计划项不存在")
    await ensure_project_access(db, plan_item.project_id, current_user, require_manage=True)

    from app.utils.soft_delete import soft_delete

    # 软删除关联的检查任务
    if plan_item.inspection_task_id:
        inspection_task = await db.get(InspectionTask, plan_item.inspection_task_id)
        if inspection_task and not inspection_task.is_deleted:
            await soft_delete(db, inspection_task, unique_fields=["task_no"])

    # 软删除计划项本身
    await soft_delete(db, plan_item)
    await db.commit()
    return make_response(message="审核计划项及关联的检查任务已删除")


# ==================== AuditAreaRecord Routes ====================

@router.post("/{project_id}/records")
async def create_area_record(
    project_id: UUID,
    record: AuditAreaRecordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建审核区域记录"""
    await ensure_project_access(db, project_id, current_user)
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
    await ensure_project_access(db, project_id, current_user)
    query = select(AuditAreaRecord).where(AuditAreaRecord.project_id == project_id)

    if area_id:
        query = query.where(AuditAreaRecord.area_id == area_id)
    if status:
        query = query.where(AuditAreaRecord.status == status)

    query = query.options(
        selectinload(AuditAreaRecord.area),
        selectinload(AuditAreaRecord.plan_item),
        selectinload(AuditAreaRecord.items),
    ).order_by(AuditAreaRecord.created_at.desc())
    result = await db.execute(query)
    return make_response([area_record_response(item) for item in result.scalars().all()])


@router.get("/records/{record_id}")
async def get_area_record(
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取审核区域记录详情"""
    result = await db.execute(
        select(AuditAreaRecord)
        .where(AuditAreaRecord.id == record_id)
        .options(
            selectinload(AuditAreaRecord.area),
            selectinload(AuditAreaRecord.plan_item),
            selectinload(AuditAreaRecord.items),
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="审核区域记录不存在")
    await ensure_project_access(db, record.project_id, current_user)
    return make_response(area_record_response(record))


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
    await ensure_project_access(db, record.project_id, current_user)

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
    await ensure_project_access(db, project_id, current_user)
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
    await ensure_project_access(db, project_id, current_user)
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
    await ensure_project_access(db, nc.project_id, current_user, require_manage=True)

    update_data = nc_update.model_dump(exclude_unset=True)
    _validate_nonconformity_transition(nc, update_data)
    for field, value in update_data.items():
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
    await ensure_project_access(db, project_id, current_user, require_manage=True)
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
    await ensure_project_access(db, project_id, current_user)
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
    await ensure_project_access(db, report.project_id, current_user, require_manage=True)

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
    await ensure_project_access(db, project_id, current_user, require_manage=True)

    # 首/末次会议在同一项目内唯一（BUG-26）；阶段沟通/内部会议允许多次
    if meeting.meeting_type in ("opening", "closing"):
        dup = await db.execute(
            select(CommunicationMeeting.id)
            .where(
                CommunicationMeeting.project_id == project_id,
                CommunicationMeeting.meeting_type == meeting.meeting_type,
            )
            .limit(1)
        )
        if dup.scalars().first() is not None:
            raise HTTPException(
                status_code=409,
                detail="该项目已存在同类型会议记录，请编辑已有记录或选择其他会议类型",
            )

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
    await ensure_project_access(db, project_id, current_user)
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
    await ensure_project_access(db, meeting.project_id, current_user, require_manage=True)

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
    await ensure_project_access(db, project_id, current_user)
    # 获取所有计划项
    plan_items_result = await db.execute(
        select(AuditPlanItem).where(
            AuditPlanItem.project_id == project_id,
            AuditPlanItem.is_deleted == False,  # noqa: E712
        )
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
    await ensure_project_access(db, project_id, current_user)
    quality = await project_artifact_service.quality_check(db, project_id)
    if not quality["passed"]:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "完整性和一致性检查未通过，不能导出正式审核报告",
                "quality_check": quality,
            },
        )

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
    await ensure_project_access(db, project_id, current_user)
    quality = await project_artifact_service.quality_check(db, project_id)
    if not quality["passed"]:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "完整性和一致性检查未通过，不能导出正式审核报告",
                "quality_check": quality,
            },
        )

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
    stream_prepare_audit_with_ai,
    stream_generate_report_with_ai,
)

@router.post("/{project_id}/ai/prepare")
async def ai_prepare_audit(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 审核准备建议"""
    await ensure_project_access(db, project_id, current_user)
    try:
        result = await prepare_audit_with_ai(db, project_id, user_id=str(current_user.id))
        return {"code": 200, "message": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 服务失败: {str(e)}")


@router.post("/{project_id}/ai/prepare/stream")
async def ai_prepare_audit_stream(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 审核准备建议（流式 SSE）"""
    await ensure_project_access(db, project_id, current_user)

    async def event_generator():
        try:
            async for chunk in stream_prepare_audit_with_ai(
                db, project_id, user_id=str(current_user.id)
            ):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
    await ensure_project_access(db, project_id, current_user)
    try:
        result = await evaluate_evidence_with_ai(db, evidence, clause_no, certification_system, user_id=str(current_user.id))
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
    await ensure_project_access(db, project_id, current_user, require_manage=True)
    try:
        result = await generate_report_with_ai(db, project_id, user_id=str(current_user.id))
        return {"code": 200, "message": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 服务失败: {str(e)}")


@router.post("/{project_id}/ai/generate-report/stream")
async def ai_generate_report_stream(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 生成审核报告叙述性评价（流式 SSE）"""
    await ensure_project_access(db, project_id, current_user, require_manage=True)

    async def event_generator():
        try:
            async for chunk in stream_generate_report_with_ai(
                db, project_id, user_id=str(current_user.id)
            ):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
    await ensure_project_access(db, project_id, current_user)
    try:
        result = await suggest_nc_with_ai(db, evidence, clause_no, certification_system, user_id=str(current_user.id))
        return {"code": 200, "message": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 服务失败: {str(e)}")

