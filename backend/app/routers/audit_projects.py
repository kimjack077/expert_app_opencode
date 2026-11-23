"""
审核项目 API 路由
Audit Projects API Routes
"""
import json
from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.database import get_db
from app.services.project_access_service import (
    ensure_project_access,
    project_visibility_condition,
)
from app.utils.response import make_response
from app.utils.category import is_category_node, load_parent_ids, parent_id_subquery
from app.utils.activity import is_meeting_activity, requires_template
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
from app.models.record import InspectionRecordItem
from app.models.template import TemplateItem
from app.models.user import User
from app.models.enterprise import Enterprise
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
    AuditAreaRecordItemsUpdate,
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
    AiNcSuggestRequest,
    AiEvidenceEvaluationRequest,
)
from app.utils.security import get_current_user, get_current_user_optional, get_user_from_token
from app.utils.item_stats import classify_item, classify_result
from app.utils.item_completion import is_item_assessed, resolve_check_type
from app.utils.item_write_guard import validate_item_payload
from app.utils.roles import is_admin
from app.utils.meeting_guard import (
    duplicate_meeting_message,
    find_duplicate_meeting,
)

router = APIRouter(prefix="/api/audit-projects", tags=["audit-projects"])




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
    # 响应侧提供统一展示字段，快照仅由服务端维护，不作为客户端可写字段。
    for item in value.get("items", []):
        for field in ("check_type", "result_options", "min_value", "max_value", "unit"):
            if item.get(f"item_{field}") is not None:
                item[field] = item[f"item_{field}"]
    value["items_count"] = len(items)
    # 原实现用 `result == "pass" or evaluation_3level in {"1","2"}` 的 `or` 组合，
    # 存在两个缺陷：① 一个条目可能同时计入合格与不合格（双计）；
    # ② 完全忽略 radio_value —— 而 PC/H5 主路径写的就是 radio_value，
    # 导致审核项目列表的合格数远小于详情页。
    # classify_item 按 radio_value → result → evaluation_3level 优先级取**唯一**归类。
    buckets = [classify_item(i) for i in items]
    value["pass_count"] = sum(1 for b in buckets if b == "pass")
    value["fail_count"] = sum(1 for b in buckets if b == "fail")
    value["na_count"] = sum(1 for b in buckets if b == "na")
    return value


def _has_area_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return str(value).strip().lower() not in {"", "null"}


def _area_item_assessed(item: Any, template: Any = None) -> bool:
    """区域填报复用类型判据；显式不适用适用于所有类型，0 是有效值。"""
    source = template if template is not None else item
    get_type = source.get if isinstance(source, dict) else lambda key: getattr(source, key, None)
    kind = get_type("check_type") or get_type("item_check_type")
    get_value = item.get if isinstance(item, dict) else lambda key: getattr(item, key, None)
    if classify_item(item) == "na":
        return True
    if kind == "checkbox":
        return _has_area_value(get_value("multi_value"))
    if kind == "photo":
        return _has_area_value(get_value("photos"))
    return is_item_assessed(source, item)


def _start_audit_project(project: AuditProject, now: datetime) -> None:
    if project.status == "planning":
        project.status = "in_progress"
        project.actual_start = project.actual_start or now


async def _sync_project_after_area_plan(
    db: AsyncSession, project: AuditProject, plan_item: AuditPlanItem, now: datetime,
) -> None:
    """仅同步状态，不调用会覆盖区域检查项的 task→formal 数据复制。"""
    if project.status in {"cancelled", "completed"}:
        return
    _start_audit_project(project, now)
    remaining = (await db.execute(
        select(func.count(AuditPlanItem.id)).where(
            AuditPlanItem.project_id == project.id,
            AuditPlanItem.is_deleted == False,  # noqa: E712
            AuditPlanItem.id != plan_item.id,
            AuditPlanItem.status != "completed",
        )
    )).scalar() or 0
    if not remaining:
        project.status = "completed"
        project.actual_end = project.actual_end or now


def _task_progress_fields(
    plan_item: AuditPlanItem,
    record: AuditAreaRecord | None = None,
    nonconformities: list[Nonconformity] | None = None,
    template_item_count: int = 0,
    confirmed_record_count: int | None = None,
    record_exceptions: int | None = None,
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

    if confirmed_record_count is None or record_exceptions is None:
        record_items = [
            item for item in (getattr(record, "items", None) or [])
            if not is_category_node(item) and _area_item_assessed(item)
        ]
        if confirmed_record_count is None:
            confirmed_record_count = len(record_items)
        if record_exceptions is None:
            record_exceptions = sum(classify_item(item) == "fail" for item in record_items)

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
    # 检查企业是否存在且未删除
    enterprise = await db.get(Enterprise, project.enterprise_id)
    if not enterprise or enterprise.is_deleted:
        raise HTTPException(status_code=404, detail="Enterprise not found")

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

    # PERF：窗口函数随分页查询一次取回数据 + total，任何页都只需 1 次 DB 往返。
    query = (
        select(AuditProject)
        .where(and_(*conditions))
        .add_columns(func.count().over().label("_total"))
        .order_by(AuditProject.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = (await db.execute(query)).all()
    projects = [row[0] for row in rows]
    total = int(rows[0][1]) if rows else 0

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

    注意：必须过滤「所属项目已软删除」的计划项。项目删除后计划项不会级联删除，
    若此处放行，任务会照常出现在列表里，但点进详情时项目鉴权接口
    （ensure_project_access → get_project_or_404，带 is_deleted 过滤）会返回 404，
    用户看到的是「查看结果报错」而不是「任务已归档」。
    """
    # 优化：通过 joinedload 一次性加载关联的项目与企业，彻底消除后续两次额外查询
    query = (
        select(AuditPlanItem)
        .join(AuditProject, AuditProject.id == AuditPlanItem.project_id)
        .options(
            joinedload(AuditPlanItem.project).joinedload(AuditProject.enterprise)
        )
        .where(
            AuditPlanItem.assigned_member_ids.contains([current_user.id]),
            AuditPlanItem.is_deleted == False,  # noqa: E712
            AuditProject.is_deleted == False,  # noqa: E712
        )
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

    plan_item_ids = [item.id for item in plan_items if item.id]
    latest_records_by_plan: dict[UUID, AuditAreaRecord] = {}
    record_stats_by_id: dict[UUID, tuple[int, int]] = {}
    nonconformities_by_plan: dict[UUID, list[Nonconformity]] = {}
    template_item_counts: dict[UUID, int] = {}

    if plan_item_ids:
        # 查询各计划项关联的最新区域记录（不级联加载海量 items 大字段）
        records = (
            await db.execute(
                select(AuditAreaRecord)
                .where(AuditAreaRecord.plan_item_id.in_(plan_item_ids))
                .order_by(AuditAreaRecord.created_at.desc())
            )
        ).scalars().all()
        for record in records:
            if record.plan_item_id:
                latest_records_by_plan.setdefault(record.plan_item_id, record)

        latest_record_ids = [r.id for r in latest_records_by_plan.values() if r.id]
        if latest_record_ids:
            # 批量只取完成判据需要的字段，不按占位行数计完成，也不加载证据等大字段。
            item_stats_rows = (
                await db.execute(
                    select(
                        InspectionRecordItem.audit_area_record_id,
                        InspectionRecordItem.template_item_id,
                        InspectionRecordItem.item_check_type,
                        InspectionRecordItem.radio_value,
                        InspectionRecordItem.result,
                        InspectionRecordItem.evaluation_3level,
                        InspectionRecordItem.numeric_value,
                        InspectionRecordItem.score_value,
                        InspectionRecordItem.text_value,
                        InspectionRecordItem.multi_value,
                        InspectionRecordItem.result_value,
                        InspectionRecordItem.result_text,
                        InspectionRecordItem.photos,
                        TemplateItem.check_type,
                        TemplateItem.result_type,
                    )
                    .outerjoin(TemplateItem, TemplateItem.id == InspectionRecordItem.template_item_id)
                    .where(
                        InspectionRecordItem.audit_area_record_id.in_(latest_record_ids),
                        or_(
                            InspectionRecordItem.template_item_id.is_(None),
                            and_(
                                TemplateItem.is_deleted == False,  # noqa: E712
                                TemplateItem.is_category.is_not(True),
                                TemplateItem.id.not_in(parent_id_subquery()),
                            ),
                        ),
                    )
                )
            ).mappings().all()
            for row in item_stats_rows:
                item = dict(row)
                if not _area_item_assessed(item):
                    continue
                r_id = item["audit_area_record_id"]
                total_cnt, exc_cnt = record_stats_by_id.get(r_id, (0, 0))
                record_stats_by_id[r_id] = (total_cnt + 1, exc_cnt + (classify_item(item) == "fail"))

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
            item_count_query = (
                select(TemplateItem.template_id, func.count(TemplateItem.id))
                .where(
                    TemplateItem.template_id.in_(template_ids),
                    TemplateItem.is_deleted == False,  # noqa: E712
                    TemplateItem.is_category.is_not(True),
                )
            )
            if parent_ids:
                item_count_query = item_count_query.where(TemplateItem.id.not_in(parent_ids))
            item_count_rows = (
                await db.execute(item_count_query.group_by(TemplateItem.template_id))
            ).all()
            for tid, count in item_count_rows:
                template_item_counts[tid] = int(count or 0)

    payload = []
    for item in plan_items:
        project = item.project
        enterprise = project.enterprise if project else None
        record = latest_records_by_plan.get(item.id)
        confirmed_count, record_exceptions = (
            record_stats_by_id.get(record.id, (0, 0)) if record else (0, 0)
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
                    record,
                    nonconformities_by_plan.get(item.id, []),
                    template_item_counts.get(item.template_id, 0) if item.template_id else 0,
                    confirmed_record_count=confirmed_count,
                    record_exceptions=record_exceptions,
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
    """删除审核项目（软删除）

    项目是**聚合根**：区域、组员、会议、不符合项、报告、证据、AI 会话
    在项目消失后都失去归属与展示入口。删除项目即删除该项目下的全部项目级数据，
    由 ``FK_CASCADE_POLICY`` 统一登记与执行。

    关键修复（外部测试 P0-29）：``audit_plan_items`` 此前不随项目软删，
    导致「我的审核任务」列出这些计划项、点进去必定 404。
    现登记为 CASCADE_SOFT（可逆），计划项与项目状态保持一致。

    响应中的 ``cascaded`` 给出各子表实际影响行数，供前端提示
    「将删除 N 项关联数据」并写入审计日志。
    """
    await ensure_project_access(db, project_id, current_user, require_manage=True)
    result = await db.execute(
        select(AuditProject).where(AuditProject.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project or project.is_deleted:
        raise HTTPException(status_code=404, detail="审核项目不存在")

    from app.utils.soft_delete import soft_delete_cascade

    # 软删除项目本身（project_no 唯一字段需追加后缀避免冲突）+ 按策略级联
    affected = await soft_delete_cascade(db, project, unique_fields=["project_no"])
    await db.commit()
    return make_response(message="审核项目已删除", data={"cascaded": affected})


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

    update_fields = plan_item_update.model_dump(exclude_unset=True)
    # 「我的审核任务」的"开始"是被分配成员的日常操作：仅改 status 时
    # 放宽到项目成员即可；其余字段变更仍要求项目管理权限。
    status_only = set(update_fields) == {"status"}
    project = await ensure_project_access(
        db, plan_item.project_id, current_user, require_manage=not status_only
    )
    old_status = plan_item.status
    if "status" in update_fields:
        new_status = update_fields["status"]
        if new_status not in ("pending", "in_progress", "completed", "cancelled"):
            raise HTTPException(status_code=422, detail="无效的计划项状态")
        if plan_item.inspection_task_id and new_status in {"completed", "cancelled"}:
            raise HTTPException(
                status_code=409,
                detail="关联任务的计划项请通过任务完成/取消接口，或提交区域记录完成",
            )
        if old_status in {"completed", "cancelled"} and new_status != old_status:
            raise HTTPException(status_code=409, detail="已结束的计划项不能回退状态")
        if plan_item.inspection_task_id and old_status == "in_progress" and new_status == "pending":
            raise HTTPException(status_code=409, detail="已开始的关联计划项不能回退状态")
        is_manager = (
            is_admin(current_user.role)
            or str(project.created_by) == str(current_user.id)
            or str(project.team_leader_id) == str(current_user.id)
        )
        if status_only and not is_manager and not (
            old_status == "pending" and new_status == "in_progress"
        ):
            raise HTTPException(status_code=403, detail="仅项目负责人可变更为此状态")

    starting = old_status == "pending" and update_fields.get("status") == "in_progress"
    inspection_task = None
    if plan_item.inspection_task_id:
        inspection_task = await db.get(InspectionTask, plan_item.inspection_task_id)
        if starting and (
            not inspection_task or inspection_task.is_deleted
            or inspection_task.status not in {"pending", "in_progress"}
        ):
            raise HTTPException(status_code=409, detail="关联任务当前状态不允许开始")
    if starting and project.status in {"cancelled", "completed"}:
        raise HTTPException(status_code=409, detail="已结束的审核项目不能开始计划项")

    # 更新审核计划项字段
    for field, value in update_fields.items():
        setattr(plan_item, field, value)

    # 合并后的最终状态必须是「检查类活动有模板」。Schema 只能看到请求体里
    # 显式给出的字段，这里用库里的现值补齐（例如只改 activity_type 的场景）。
    if requires_template(plan_item.activity_type) and not plan_item.template_id:
        raise HTTPException(
            status_code=400,
            detail="请选择检查模板（检查类审核活动必须绑定检查模板）",
        )

    now = datetime.now(timezone.utc)
    if starting:
        _start_audit_project(project, now)
        if inspection_task:
            inspection_task.status = "in_progress"
            inspection_task.started_at = inspection_task.started_at or now
    elif old_status != "completed" and plan_item.status == "completed":
        # 无关联任务的会议等计划仍可正常完成。
        await _sync_project_after_area_plan(db, project, plan_item, now)

    # 只改状态不应顺带重建任务检查项；其余编辑保留已有的元数据同步。
    if not status_only and plan_item.inspection_task_id:
        if inspection_task:
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
                # 检查关联任务是否缺少检查项记录，若缺少则根据模板自动生成
                existing_recs_count = (await db.execute(
                    select(func.count(TaskItemRecord.id)).where(TaskItemRecord.task_id == inspection_task.id)
                )).scalar() or 0
                if existing_recs_count == 0:
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
    """删除审核计划项（软删除），同时软删除关联的检查任务

    级联说明：

    * 关联检查任务走 ``soft_delete_cascade`` —— ``task_item_records`` 是硬删除表，
      任务软删后其明细会成为永久孤儿（实测 186 条），必须随任务清除。
    * 计划项自身仅级联 ``ai_draft_records``（可重生成的过程缓存）。
      不符合项 / 证据提交 / 现场检查记录均登记为 **PRESERVE**：
      移除一项检查任务是日常操作，不得销毁已判定的业务结论与证据
      （见 ``test_plan_item_removal_must_not_destroy_business_conclusions``）。
    """
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

    from app.utils.soft_delete import soft_delete_cascade

    affected: dict[str, int] = {}

    # 软删除关联的检查任务（含其明细，见 FK_CASCADE_POLICY）
    if plan_item.inspection_task_id:
        inspection_task = await db.get(InspectionTask, plan_item.inspection_task_id)
        if inspection_task and not inspection_task.is_deleted:
            for table_name, count in (
                await soft_delete_cascade(db, inspection_task, unique_fields=["task_no"])
            ).items():
                affected[table_name] = affected.get(table_name, 0) + count

    # 软删除计划项本身
    for table_name, count in (await soft_delete_cascade(db, plan_item)).items():
        affected[table_name] = affected.get(table_name, 0) + count

    await db.commit()
    return make_response(
        message="审核计划项及关联的检查任务已删除",
        data={"cascaded": affected},
    )


# ==================== AuditAreaRecord Routes ====================

@router.post("/{project_id}/records")
async def create_area_record(
    project_id: UUID,
    record: AuditAreaRecordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建审核区域记录"""
    project = await ensure_project_access(db, project_id, current_user)
    record_no = f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"

    db_record = AuditAreaRecord(
        project_id=project_id,
        record_no=record_no,
        recorded_by=current_user.id,
        **record.model_dump(exclude={"items", "status"}),
        items=[], status="draft",
    )
    db.add(db_record)
    await db.flush()
    await _save_area_record_items(db, db_record, record.items)
    if record.status == "submitted":
        await _submit_area_record(db, db_record, project, {"status": "submitted"})
    else:
        db_record.status = record.status
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


async def _submit_area_record(
    db: AsyncSession, record: AuditAreaRecord, project: AuditProject, updates: dict,
) -> None:
    """校验区域自身的填报并推进状态，绝不从任务流反向覆盖检查项。"""
    if not _has_area_value(updates.get("conclusion", record.conclusion)):
        raise HTTPException(status_code=422, detail="请填写最终审核结论后再提交")
    if project.status == "cancelled":
        raise HTTPException(status_code=409, detail="已取消的审核项目不能提交记录")

    plan = await db.get(AuditPlanItem, record.plan_item_id) if record.plan_item_id else None
    if record.plan_item_id and (not plan or plan.is_deleted or plan.project_id != record.project_id):
        raise HTTPException(status_code=409, detail="关联审核计划项不可用")
    if plan and plan.status == "cancelled":
        raise HTTPException(status_code=409, detail="已取消的计划项不能提交记录")

    template_id = updates.get("template_id", record.template_id) or (plan.template_id if plan else None)
    if plan and plan.template_id and template_id != plan.template_id:
        raise HTTPException(status_code=422, detail="区域记录模板必须与关联计划项一致")
    if plan and requires_template(plan.activity_type) and not template_id:
        raise HTTPException(status_code=422, detail="检查类审核活动必须绑定检查模板")

    items = list(record.items or [])
    if template_id:
        templates = (await db.execute(select(TemplateItem).where(
            TemplateItem.template_id == template_id,
            TemplateItem.is_deleted == False,  # noqa: E712
        ))).scalars().all()
        parent_ids = {item.parent_id for item in templates if item.parent_id}
        leaves = {item.id: item for item in templates if not is_category_node(item, parent_ids)}
        assessed_ids = {
            item.template_item_id for item in items
            if item.template_item_id in leaves
            and _area_item_assessed(item, leaves[item.template_item_id])
        }
        missing = [item.title for item in leaves.values() if item.is_required and item.id not in assessed_ids]
        if missing:
            raise HTTPException(
                status_code=422, detail=f"存在未填报的必填检查项：{'、'.join(missing[:3])}",
            )
        has_assessed = bool(assessed_ids)
    else:
        has_assessed = any(_area_item_assessed(item) for item in items)
    if not has_assessed:
        raise HTTPException(status_code=422, detail="请先完成至少一项检查记录，再提交")

    task = await db.get(InspectionTask, plan.inspection_task_id) if plan and plan.inspection_task_id else None
    if plan and plan.inspection_task_id and (not task or task.is_deleted or task.status == "cancelled"):
        raise HTTPException(status_code=409, detail="关联任务当前状态不允许提交")
    area_id = updates.get("area_id", record.area_id)
    area = await db.get(AuditArea, area_id) if area_id else None
    if area_id and (not area or area.project_id != record.project_id):
        raise HTTPException(status_code=422, detail="关联审核区域不可用")
    if not area and plan:
        area = (await db.execute(select(AuditArea).where(
            AuditArea.project_id == record.project_id,
            AuditArea.area_name == plan.area_name,
        ).order_by(AuditArea.created_at.desc()).limit(1))).scalars().first()
        if not area:
            area = AuditArea(
                project_id=record.project_id, area_name=plan.area_name, area_type=plan.area_type,
                responsible_team_member_ids=plan.assigned_member_ids or [],
                audit_clauses=plan.clauses or [], status="completed",
            )
            db.add(area)
            await db.flush()

    for field, value in updates.items():
        setattr(record, field, value)
    record.template_id = template_id
    record.status = "submitted"
    if area:
        record.area_id = area.id
        area.status = "completed"
    now = datetime.now(timezone.utc)
    if task:
        task.status = "completed"
        task.started_at = task.started_at or now
        task.completed_at = task.completed_at or now
    if plan:
        plan.status = "completed"
        await _sync_project_after_area_plan(db, project, plan, now)
    else:
        _start_audit_project(project, now)


@router.put("/records/{record_id}")
async def update_area_record(
    record_id: UUID,
    record_update: AuditAreaRecordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新审核区域记录；提交必须校验并同步关联业务状态。"""
    result = await db.execute(
        select(AuditAreaRecord).where(AuditAreaRecord.id == record_id)
        .options(selectinload(AuditAreaRecord.items))
        .with_for_update()
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="审核区域记录不存在")
    project = await ensure_project_access(db, record.project_id, current_user)

    # 验证权限：只有主填写人或协作填写人可以更新
    if record.recorded_by != current_user.id and current_user.id not in (record.co_recorders or []):
        raise HTTPException(status_code=403, detail="无权限更新此记录")

    updates = record_update.model_dump(exclude_unset=True)
    if record.status == "submitted":
        if updates == {"status": "submitted"}:
            return make_response(record)
        raise HTTPException(status_code=409, detail="该审核记录已提交，不可修改或退回")
    if "status" in updates and updates["status"] is None:
        raise HTTPException(status_code=422, detail="无效的区域记录状态")
    updates.pop("items", None)
    if "template_id" in updates and record.template_id and updates["template_id"] != record.template_id and record.items:
        raise HTTPException(status_code=409, detail="已有填报明细的记录不可切换模板，请新建记录")
    # 先应用表头，再在同一事务写明细及校验提交；任一步失败均由 get_db 回滚。
    for field, value in updates.items():
        if field != "status":
            setattr(record, field, value)
    if record_update.items is not None:
        await _save_area_record_items(db, record, record_update.items)
    if updates.get("status") == "submitted":
        await _submit_area_record(db, record, project, updates)
    else:
        for field, value in updates.items():
            setattr(record, field, value)

    await db.commit()
    await db.refresh(record)
    return make_response(record)


@router.put("/records/{record_id}/items")
async def update_area_record_items(
    record_id: UUID,
    payload: AuditAreaRecordItemsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量保存区域记录检查项 —— AuditRecordEdit 抽屉填报的落库入口。

    此前前端只提交表头字段，抽屉里填的判定/证据/照片刷新即丢（P0 数据丢失）。
    按 id 或 (记录, template_item_id) 匹配既有项，缺失则按模板创建并补快照。
    """
    result = await db.execute(
        select(AuditAreaRecord)
        .where(AuditAreaRecord.id == record_id)
        .options(selectinload(AuditAreaRecord.items))
        .with_for_update()
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="审核区域记录不存在")
    await ensure_project_access(db, record.project_id, current_user)

    # 与 update_area_record 同一口径：主填写人或协作填写人可写
    if record.recorded_by != current_user.id and current_user.id not in (
        record.co_recorders or []
    ):
        raise HTTPException(status_code=403, detail="无权限更新此记录")
    if record.status == "submitted":
        raise HTTPException(status_code=409, detail="该审核记录已提交，检查项不可再修改")

    saved = await _save_area_record_items(db, record, payload.items)
    await db.commit()
    return make_response(data={"saved": saved}, message="检查项已保存")


async def _save_area_record_items(db: AsyncSession, record: AuditAreaRecord, entries) -> int:
    """复用保存逻辑，不提交事务；拒绝混入其它模板及重复检查项。"""
    plan = await db.get(AuditPlanItem, record.plan_item_id) if record.plan_item_id else None
    if record.plan_item_id and (not plan or plan.is_deleted or plan.project_id != record.project_id):
        raise HTTPException(status_code=422, detail="关联审核计划项不可用")
    template_id = record.template_id or (plan.template_id if plan else None)
    if plan and plan.template_id and template_id != plan.template_id:
        raise HTTPException(status_code=422, detail="区域记录模板必须与关联计划项一致")
    parent_ids = await load_parent_ids(db, template_id=template_id) if template_id else set()
    existing_by_id = {str(i.id): i for i in record.items or []}
    existing_by_template = {
        str(i.template_item_id): i for i in record.items or [] if i.template_item_id
    }

    writable_fields = (
        "result",
        "radio_value",
        "evaluation_3level",
        "score_value",
        "numeric_value",
        "text_value",
        "multi_value",
        "audit_evidence",
        "audit_findings",
        "rectification_suggestion",
        "inspector_note",
        "photos",
    )

    saved = 0
    seen = set()
    for entry in entries:
        data = entry.normalized_updates()
        item = None
        if entry.id is not None:
            item = existing_by_id.get(str(entry.id))
            if item is None:
                raise HTTPException(
                    status_code=404, detail=f"检查项 {entry.id} 不属于该记录"
                )
        elif entry.template_item_id is not None:
            item = existing_by_template.get(str(entry.template_item_id))

        template_item_id = item.template_item_id if item else entry.template_item_id
        if item and entry.template_item_id and entry.template_item_id != item.template_item_id:
            raise HTTPException(status_code=422, detail="记录项与模板项不一致")
        if template_item_id in seen:
            raise HTTPException(status_code=422, detail="不能重复保存同一检查项")
        seen.add(template_item_id)
        template = await db.get(TemplateItem, template_item_id) if template_item_id else None
        if template_item_id and (
            not template or template.is_deleted or not template_id
            or str(template.template_id) != str(template_id)
        ):
            raise HTTPException(status_code=422, detail="检查项不属于当前记录模板")
        if is_category_node(template, parent_ids):
            raise HTTPException(status_code=422, detail="分类目录不能填写检查结果")
        has_snapshot = bool(item and item.item_check_type)
        kind = resolve_check_type(item if has_snapshot else template)
        validation_data = dict(data)
        # 不适用在各类检查项均可表达；其它值按当前类型校验。
        if classify_result(data.get("radio_value")) == "na":
            validation_data.pop("radio_value", None)
        errors = validate_item_payload(
            check_type=None if kind == "photo" else kind,
            payload=validation_data,
            result_options=item.item_result_options if has_snapshot else (template.result_options if template else None),
            allowed_result_values=["pass", "fail", "na", "pending_rectification", "observe"] if kind in {"radio", "audit_3level"} else None,
        )
        if errors:
            raise HTTPException(status_code=422, detail="；".join(errors))

        if item is None:
            if entry.template_item_id is None:
                raise HTTPException(
                    status_code=422, detail="新建检查项必须提供 template_item_id"
                )
            # 未填写的新模板项不创建占位行；既有项仍须执行下面的显式清空。
            if not entry.ensure_exists and not any(_has_area_value(data.get(field)) for field in writable_fields):
                continue
            item = InspectionRecordItem(
                audit_area_record_id=record.id,
                template_item_id=entry.template_item_id,
                item_title=template.title,
                item_description=template.description,
                item_check_method=template.check_method,
                item_legal_basis=template.legal_basis,
                item_standard_ref=template.standard_ref,
                item_risk_level=template.risk_level,
                item_check_type=resolve_check_type(template),
                item_result_options=template.result_options,
                item_min_value=template.min_value,
                item_max_value=template.max_value,
                item_unit=template.unit,
                item_score_weight=template.score_weight,
                item_default_score=template.default_score,
                item_allow_attachment=bool(template.allow_attachment),
                item_attachment_required=bool(template.attachment_required),
            )
            record.items.append(item)
            db.add(item)
            await db.flush()
            existing_by_id[str(item.id)] = item
            existing_by_template[str(entry.template_item_id)] = item

        for field in writable_fields:
            if field in data:
                setattr(item, field, data[field])

        # 清空新字段时同步清掉旧兼容值，否则完成判据仍会读到上一次的填写。
        kind = resolve_check_type(item)
        value_field = {"numeric": "numeric_value", "score": "score_value"}.get(kind)
        if value_field and value_field in data:
            item.result_value = data[value_field]
        if kind == "text" and "text_value" in data:
            item.result_text = data["text_value"]
        item.updated_at = datetime.now(timezone.utc)
        saved += 1

    await db.flush()
    return saved


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


@router.delete("/nonconformities/{nc_id}")
async def delete_nonconformity(
    nc_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除不符合项"""
    result = await db.execute(
        select(Nonconformity).where(Nonconformity.id == nc_id)
    )
    nc = result.scalar_one_or_none()
    if not nc:
        raise HTTPException(status_code=404, detail="不符合项不存在")
    await ensure_project_access(db, nc.project_id, current_user, require_manage=True)
    await db.delete(nc)
    await db.commit()
    return make_response({"id": str(nc_id), "deleted": True}, message="不符合项已删除")


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

    # BUG-36：body 中的 project_id 已可选；若传入需与路径一致
    if report.project_id and report.project_id != project_id:
        raise HTTPException(
            status_code=422,
            detail="请求体中的 project_id 与 URL 路径不一致",
        )

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

    # BUG-36：body 中的 project_id 已可选；若传入需与路径一致
    if meeting.project_id and meeting.project_id != project_id:
        raise HTTPException(
            status_code=422,
            detail="请求体中的 project_id 与 URL 路径不一致",
        )

    # 首/末次会议在同一项目内唯一（BUG-26）；阶段沟通/内部会议允许多次。
    # 口径统一走 app.utils.meeting_guard，与 Agent 写入路径共用同一判据。
    if await find_duplicate_meeting(db, project_id, meeting.meeting_type) is not None:
        raise HTTPException(
            status_code=409,
            detail=duplicate_meeting_message(meeting.meeting_type),
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


@router.delete("/meetings/{meeting_id}")
async def delete_meeting(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除沟通会议记录"""
    result = await db.execute(
        select(CommunicationMeeting).where(CommunicationMeeting.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="沟通会议记录不存在")
    await ensure_project_access(db, meeting.project_id, current_user, require_manage=True)
    await db.delete(meeting)
    await db.commit()
    return make_response({"id": str(meeting_id), "deleted": True}, message="会议记录已删除")


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
    all_ncs = nc_result.scalars().all()
    # 已驳回的 AI 草稿不是正式不符合项，不计入项目 NC 数（此前顶部「不符合项 (N)」把它也算进去）
    nonconformities = [nc for nc in all_ncs if (nc.status or "") != "rejected"]
    # 等待人工确认的 AI 草稿单独计数，便于界面提示
    draft_ncs = sum(1 for nc in nonconformities if (nc.status or "") == "draft")
    open_ncs = sum(1 for nc in nonconformities if (nc.status or "") not in ("draft", "verified", "closed"))

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
            "open": open_ncs,
            "draft": draft_ncs,
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
    token: Optional[str] = Query(None, description="认证令牌（兼容旧版；建议改用 Authorization 头）"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """导出 Word 格式审核报告

    鉴权优先级：``Authorization: Bearer <token>`` > ``?token=<token>``。
    后者仅用于兼容旧前端，会在后续版本中移除。
    """
    if current_user is None:
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
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
    token: Optional[str] = Query(None, description="认证令牌（兼容旧版；建议改用 Authorization 头）"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """导出 PDF 格式审核报告

    鉴权优先级：``Authorization: Bearer <token>`` > ``?token=<token>``。
    后者仅用于兼容旧前端，会在后续版本中移除。
    """
    if current_user is None:
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
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
    evidence: Optional[str] = Query(None, description="审核现场证据（兼容 query 参数）"),
    clause_no: Optional[str] = Query(None, description="标准条款号（兼容 query 参数）"),
    certification_system: Optional[str] = Query(None, description="认证体系代码（兼容 query 参数）"),
    body: Optional[AiEvidenceEvaluationRequest] = Body(None, description="请求体参数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 证据充分性评估（同时兼容 JSON Body 与 Query 参数）"""
    await ensure_project_access(db, project_id, current_user)
    ev = (body.evidence if body and body.evidence is not None else None) or evidence
    cl = (body.clause_no if body and body.clause_no is not None else None) or clause_no
    cs = (body.certification_system if body and body.certification_system is not None else None) or certification_system
    missing = []
    if not ev:
        missing.append("evidence")
    if not cl:
        missing.append("clause_no")
    if not cs:
        missing.append("certification_system")
    if missing:
        raise HTTPException(
            status_code=422,
            detail=[
                {"loc": ["body" if body else "query", f], "msg": "Field required", "type": "missing"}
                for f in missing
            ],
        )

    try:
        result = await evaluate_evidence_with_ai(db, ev, cl, cs, user_id=str(current_user.id))
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
    evidence: Optional[str] = Query(None, description="审核现场证据（兼容 query 参数）"),
    clause_no: Optional[str] = Query(None, description="标准条款号（兼容 query 参数）"),
    certification_system: Optional[str] = Query(None, description="认证体系代码（兼容 query 参数）"),
    body: Optional[AiNcSuggestRequest] = Body(None, description="请求体参数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 建议不符合项（同时兼容 JSON Body 与 Query 参数）"""
    await ensure_project_access(db, project_id, current_user)
    ev = (body.evidence if body and body.evidence is not None else None) or evidence
    cl = (body.clause_no if body and body.clause_no is not None else None) or clause_no
    cs = (body.certification_system if body and body.certification_system is not None else None) or certification_system
    missing = []
    if not ev:
        missing.append("evidence")
    if not cl:
        missing.append("clause_no")
    if not cs:
        missing.append("certification_system")
    if missing:
        raise HTTPException(
            status_code=422,
            detail=[
                {"loc": ["body" if body else "query", f], "msg": "Field required", "type": "missing"}
                for f in missing
            ],
        )

    try:
        result = await suggest_nc_with_ai(db, ev, cl, cs, user_id=str(current_user.id))
        return {"code": 200, "message": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 服务失败: {str(e)}")

