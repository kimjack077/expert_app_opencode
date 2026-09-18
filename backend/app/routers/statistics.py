"""
审核统计 API 路由
Audit Statistics API Router

提供审核项目的统计分析数据，包括：
- 项目概览统计
- 项目分布和趋势
- 不符合项分析
- 审核员工作量统计
"""
import re
from datetime import datetime, date, timedelta, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case, literal_column
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql.functions import coalesce

from app.database import get_db
from app.models.user import User
from app.models.audit_project import (
    AuditProject,
    AuditTeamMember,
    AuditPlanItem,
    Nonconformity,
    AuditReport,
)
from app.schemas import ApiResponse
from app.utils.security import get_current_user, get_current_admin_user

router = APIRouter()

# BUG-14：条款号必须是「数字开头的层级编码」（10.88 / 8.5.2 / 2.2a 等），
# 含中文（如「把控1」）一律视为模板标题误写的脏数据，不进图表。
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_CLAUSE_TOKEN_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){0,5}[a-z]?(?:\s|$)", re.IGNORECASE)


def _normalize_clause_no(value: object) -> Optional[str]:
    """清洗条款号：去空白、全角点/间隔号归一化为半角点；非法返回 None。"""
    if value is None:
        return None
    text = str(value).strip().replace("．", ".").replace("·", ".")
    if not text or _CJK_RE.search(text):
        return None
    if not _CLAUSE_TOKEN_RE.match(text):
        return None
    return text


def make_response(data=None, code: int = 200, message: str = "success") -> ApiResponse:
    """Create standardized API response"""
    return ApiResponse(
        code=code,
        message=message,
        data=data,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/overview", response_model=ApiResponse)
async def get_overview_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    项目概览统计

    返回：
    - total: 总项目数
    - in_progress: 进行中项目数
    - completed: 已完成项目数
    - this_month: 本月新增项目数
    """
    now = datetime.now(timezone.utc)
    month_start = datetime(now.year, now.month, 1)

    # 使用单个查询获取所有统计数据
    # 注意：必须排除软删除项目，否则统计数会大于审核项目列表（列表接口是过滤的）
    stmt = (
        select(
            func.count(AuditProject.id).label("total"),
            func.count(AuditProject.id).filter(
                AuditProject.status == "in_progress"
            ).label("in_progress"),
            func.count(AuditProject.id).filter(
                AuditProject.status == "completed"
            ).label("completed"),
            func.count(AuditProject.id).filter(
                AuditProject.created_at >= month_start
            ).label("this_month"),
        )
        .where(AuditProject.is_deleted == False)  # noqa: E712
    )

    result = await db.execute(stmt)
    row = result.first()

    data = {
        "total": row.total or 0,
        "in_progress": row.in_progress or 0,
        "completed": row.completed or 0,
        "this_month": row.this_month or 0,
    }

    return make_response(data=data)


@router.get("/projects/distribution", response_model=ApiResponse)
async def get_project_distribution(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    by: str = Query("status", description="分组依据：status 或 type"),
):
    """
    项目分布统计

    参数：
    - by: 分组依据（status=按状态, type=按审核类型）

    返回：[{name, value}] 格式的分布数据
    """
    if by == "status":
        # 按状态分布（排除软删除项目，口径与审核项目列表保持一致）
        stmt = (
            select(
                AuditProject.status,
                func.count(AuditProject.id).label("count"),
            )
            .where(AuditProject.is_deleted == False)  # noqa: E712
            .group_by(AuditProject.status)
        )

        result = await db.execute(stmt)
        rows = result.all()

        status_labels = {
            "planning": "策划中",
            "in_progress": "进行中",
            "completed": "已完成",
            "cancelled": "已取消",
        }

        data = [
            {"name": status_labels.get(row.status, row.status), "value": row.count}
            for row in rows
        ]

    elif by == "type":
        # 按审核类型分布（排除软删除项目）
        stmt = (
            select(
                AuditProject.audit_type,
                func.count(AuditProject.id).label("count"),
            )
            .where(AuditProject.is_deleted == False)  # noqa: E712
            .group_by(AuditProject.audit_type)
        )

        result = await db.execute(stmt)
        rows = result.all()

        type_labels = {
            "initial": "初审",
            "surveillance": "监督审核",
            "recertification": "再认证",
            "expansion": "扩项",
        }

        data = [
            {"name": type_labels.get(row.audit_type, row.audit_type), "value": row.count}
            for row in rows
        ]

    else:
        return make_response(code=400, message="Invalid 'by' parameter. Use 'status' or 'type'.")

    return make_response(data=data)


@router.get("/projects/trend", response_model=ApiResponse)
async def get_project_trend(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    months: int = Query(6, ge=1, le=24, description="统计最近几个月"),
):
    """
    项目趋势统计

    参数：
    - months: 统计最近几个月（1-24）

    返回：[{month, created, completed}] 格式的趋势数据
    """
    now = datetime.now(timezone.utc)
    data = []

    for i in range(months - 1, -1, -1):
        # 计算月份
        month_date = datetime(now.year, now.month, 1) - timedelta(days=i * 30)
        # 修正到月初
        if month_date.month == 12 and i > 0:
            month_start = datetime(month_date.year + 1, 1, 1) - timedelta(days=i * 30)
            month_start = datetime(month_start.year, month_start.month, 1)
        else:
            month_start = datetime(month_date.year, month_date.month, 1)

        # 计算月末
        if month_start.month == 12:
            month_end = datetime(month_start.year + 1, 1, 1)
        else:
            month_end = datetime(month_start.year, month_start.month + 1, 1)

        # 查询该月创建的项目数（排除软删除项目）
        created_stmt = select(func.count(AuditProject.id)).where(
            and_(
                AuditProject.created_at >= month_start,
                AuditProject.created_at < month_end,
                AuditProject.is_deleted == False,  # noqa: E712
            )
        )
        created_count = (await db.execute(created_stmt)).scalar() or 0

        # 查询该月完成的项目数（排除软删除项目）
        completed_stmt = select(func.count(AuditProject.id)).where(
            and_(
                AuditProject.status == "completed",
                AuditProject.actual_end >= month_start,
                AuditProject.actual_end < month_end,
                AuditProject.is_deleted == False,  # noqa: E712
            )
        )
        completed_count = (await db.execute(completed_stmt)).scalar() or 0

        data.append({
            "month": month_start.strftime("%Y-%m"),
            "created": created_count,
            "completed": completed_count,
        })

    return make_response(data=data)


@router.get("/nonconformities/distribution", response_model=ApiResponse)
async def get_nc_distribution(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_id: Optional[str] = Query(None, description="筛选指定项目ID"),
):
    """
    不符合项严重程度分布

    参数：
    - project_id: 可选，筛选指定项目

    返回：[{name, value}] 格式的分布数据
    """
    # 构建基础查询（join 项目表排除软删除项目下的不符合项）
    stmt = (
        select(
            Nonconformity.severity,
            func.count(Nonconformity.id).label("count"),
        )
        .outerjoin(AuditProject, Nonconformity.project_id == AuditProject.id)
        .where(
            or_(
                Nonconformity.project_id.is_(None),
                AuditProject.is_deleted == False,  # noqa: E712
            )
        )
    )

    if project_id:
        stmt = stmt.where(Nonconformity.project_id == project_id)

    stmt = stmt.group_by(Nonconformity.severity)

    result = await db.execute(stmt)
    rows = result.all()

    severity_labels = {
        "major": "严重不符合",
        "minor": "一般不符合",
        "observation": "观察项",
    }

    # 确保所有类型都包含
    data_dict = {"major": 0, "minor": 0, "observation": 0}
    for row in rows:
        if row.severity:
            data_dict[row.severity] = row.count

    data = [
        {"name": severity_labels.get(k, k), "value": v}
        for k, v in data_dict.items()
    ]

    return make_response(data=data)


@router.get("/nonconformities/by-system", response_model=ApiResponse)
async def get_nc_by_system(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_id: Optional[str] = Query(None, description="筛选指定项目ID"),
):
    """
    不符合项按体系分布

    参数：
    - project_id: 可选，筛选指定项目

    返回：[{name, value}] 格式的分布数据
    """
    # 构建基础查询（join 项目表排除软删除项目下的不符合项）
    stmt = (
        select(
            Nonconformity.certification_system,
            func.count(Nonconformity.id).label("count"),
        )
        .outerjoin(AuditProject, Nonconformity.project_id == AuditProject.id)
        .where(
            or_(
                Nonconformity.project_id.is_(None),
                AuditProject.is_deleted == False,  # noqa: E712
            )
        )
    )

    if project_id:
        stmt = stmt.where(Nonconformity.project_id == project_id)

    stmt = stmt.group_by(Nonconformity.certification_system)

    result = await db.execute(stmt)
    rows = result.all()

    system_labels = {
        "Q": "质量体系(Q)",
        "E": "环境体系(E)",
        "S": "职业健康安全体系(S)",
        "En": "能源体系(En)",
    }

    # 初始化所有体系
    data_dict = {"Q": 0, "E": 0, "S": 0, "En": 0}
    for row in rows:
        if row.certification_system:
            data_dict[row.certification_system] = row.count

    data = [
        {"name": system_labels.get(k, k), "value": v}
        for k, v in data_dict.items()
    ]

    return make_response(data=data)


@router.get("/nonconformities/by-clause", response_model=ApiResponse)
async def get_nc_by_clause(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_id: Optional[str] = Query(None, description="筛选指定项目ID"),
    limit: int = Query(10, ge=1, le=50, description="返回数量限制"),
):
    """
    不符合项按条款TOP N

    参数：
    - project_id: 可选，筛选指定项目
    - limit: 返回数量限制

    返回：[{clause_no, count}] 格式的排序数据
    """
    # 构建基础查询（join 项目表排除软删除项目下的不符合项）
    stmt = (
        select(
            Nonconformity.clause_no,
            func.count(Nonconformity.id).label("count"),
        )
        .outerjoin(AuditProject, Nonconformity.project_id == AuditProject.id)
        .where(
            or_(
                Nonconformity.project_id.is_(None),
                AuditProject.is_deleted == False,  # noqa: E712
            )
        )
    )

    if project_id:
        stmt = stmt.where(Nonconformity.project_id == project_id)

    stmt = stmt.where(Nonconformity.clause_no.isnot(None))
    stmt = stmt.group_by(Nonconformity.clause_no)
    stmt = stmt.order_by(func.count(Nonconformity.id).desc())

    result = await db.execute(stmt)
    rows = result.all()

    # BUG-14：存量脏数据（如「把控1」「2·2」、空串）会直接进条款 TOP10 图表。
    # 这里做展示层清洗：只保留「数字开头的条款号」、剔除含中文的误写值，
    # 并把全角点/间隔号归一化后合并计数，保证图表可读且不重复。
    merged: dict[str, int] = {}
    for row in rows:
        normalized = _normalize_clause_no(row.clause_no)
        if not normalized:
            continue
        merged[normalized] = merged.get(normalized, 0) + int(row.count)

    data = [
        {"clause_no": clause, "count": count}
        for clause, count in sorted(
            merged.items(), key=lambda kv: (-kv[1], kv[0])
        )[:limit]
    ]

    return make_response(data=data)


@router.get("/nonconformities/trend", response_model=ApiResponse)
async def get_nc_trend(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    months: int = Query(6, ge=1, le=24, description="统计最近几个月"),
):
    """
    不符合项趋势统计

    参数：
    - months: 统计最近几个月（1-24）

    返回：[{month, total, major, minor, observation}] 格式的趋势数据
    """
    now = datetime.now(timezone.utc)
    data = []

    for i in range(months - 1, -1, -1):
        # 计算月份
        month_date = datetime(now.year, now.month, 1) - timedelta(days=i * 30)
        if month_date.month == 12 and i > 0:
            month_start = datetime(month_date.year + 1, 1, 1) - timedelta(days=i * 30)
            month_start = datetime(month_start.year, month_start.month, 1)
        else:
            month_start = datetime(month_date.year, month_date.month, 1)

        # 计算月末
        if month_start.month == 12:
            month_end = datetime(month_start.year + 1, 1, 1)
        else:
            month_end = datetime(month_start.year, month_start.month + 1, 1)

        # 查询该月各类不符合项数量（join 项目表排除软删除项目下的不符合项）
        stmt = select(
            func.count(Nonconformity.id).label("total"),
            func.count(Nonconformity.id).filter(
                Nonconformity.severity == "major"
            ).label("major"),
            func.count(Nonconformity.id).filter(
                Nonconformity.severity == "minor"
            ).label("minor"),
            func.count(Nonconformity.id).filter(
                Nonconformity.severity == "observation"
            ).label("observation"),
        ).outerjoin(
            AuditProject, Nonconformity.project_id == AuditProject.id
        ).where(
            and_(
                Nonconformity.created_at >= month_start,
                Nonconformity.created_at < month_end,
                or_(
                    Nonconformity.project_id.is_(None),
                    AuditProject.is_deleted == False,  # noqa: E712
                ),
            )
        )

        result = await db.execute(stmt)
        row = result.first()

        data.append({
            "month": month_start.strftime("%Y-%m"),
            "total": row.total or 0,
            "major": row.major or 0,
            "minor": row.minor or 0,
            "observation": row.observation or 0,
        })

    return make_response(data=data)


@router.get("/auditors/workload", response_model=ApiResponse)
async def get_auditor_workload(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_id: Optional[str] = Query(None, description="筛选指定项目ID"),
):
    """
    审核员工作量统计

    参数：
    - project_id: 可选，筛选指定项目

    返回：审核员工作量列表
    """
    # 查询审核员参与的项目数和区域数
    # 使用 CTE 或子查询来处理数组字段

    # 第一步：获取所有审核员及其参与的项目（排除软删除的组员关系与软删除的项目）
    active_project_ids = select(AuditProject.id).where(
        AuditProject.is_deleted == False  # noqa: E712
    ).scalar_subquery()

    atm_stmt = (
        select(
            AuditTeamMember.member_id,
            AuditTeamMember.project_id,
        )
        .where(
            AuditTeamMember.is_deleted == False,  # noqa: E712
            AuditTeamMember.project_id.in_(active_project_ids),
        )
    )

    if project_id:
        atm_stmt = atm_stmt.where(AuditTeamMember.project_id == project_id)

    # 第二步：查询开具的不符合项数（同样排除软删除项目）
    nc_stmt = select(
        Nonconformity.created_by,
        func.count(Nonconformity.id).label("nc_count"),
    ).where(
        or_(
            Nonconformity.project_id.is_(None),
            Nonconformity.project_id.in_(active_project_ids),
        )
    )

    if project_id:
        nc_stmt = nc_stmt.where(Nonconformity.project_id == project_id)

    nc_stmt = nc_stmt.group_by(Nonconformity.created_by)

    # 执行查询并手动聚合
    # 查询审核员基础信息
    users_stmt = select(User).where(
        User.role.in_(["expert", "auditor", "admin", "super_admin"]),
        User.is_deleted == False,  # noqa: E712
    )
    users_result = await db.execute(users_stmt)
    users = users_result.scalars().all()

    # 查询审核组成员关系
    atm_result = await db.execute(atm_stmt)
    atm_rows = atm_result.all()

    # 查询不符合项开具情况
    nc_result = await db.execute(nc_stmt)
    nc_rows = nc_result.all()
    nc_dict = {row.created_by: row.nc_count for row in nc_rows}

    # 聚合数据
    user_projects = {}  # user_id -> set of project_ids
    user_areas = {}  # user_id -> set of area_ids

    for row in atm_rows:
        if row.member_id not in user_projects:
            user_projects[row.member_id] = set()
            user_areas[row.member_id] = set()
        user_projects[row.member_id].add(row.project_id)

    # 查询审核区域分配（排除软删除的计划项与软删除的项目）
    api_stmt = (
        select(
            AuditPlanItem.assigned_member_ids,
            AuditPlanItem.id,
        )
        .where(
            AuditPlanItem.is_deleted == False,  # noqa: E712
            AuditPlanItem.project_id.in_(active_project_ids),
        )
    )

    if project_id:
        api_stmt = api_stmt.where(AuditPlanItem.project_id == project_id)

    api_result = await db.execute(api_stmt)
    api_rows = api_result.all()

    for row in api_rows:
        if row.assigned_member_ids:
            for member_id in row.assigned_member_ids:
                if member_id in user_areas:
                    user_areas[member_id].add(row.id)

    # 构建返回数据
    data = []
    for user in users:
        user_id_str = str(user.id)
        project_count = len(user_projects.get(user.id, set()))
        area_count = len(user_areas.get(user.id, set()))
        nc_count = nc_dict.get(user.id, 0)

        data.append({
            "user_id": user_id_str,
            "name": user.full_name or user.username,
            "project_count": project_count,
            "area_count": area_count,
            "nc_count": nc_count,
        })

    # 按项目数排序
    data.sort(key=lambda x: x["project_count"], reverse=True)

    return make_response(data=data)


@router.get("/auditors/ranking", response_model=ApiResponse)
async def get_auditor_ranking(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    metric: str = Query("projects", description="排名依据：projects/areas/ncs"),
    limit: int = Query(10, ge=1, le=50, description="返回数量限制"),
):
    """
    审核员排名

    参数：
    - metric: 排名依据（projects=项目数, areas=区域数, ncs=不符合项数）
    - limit: 返回数量限制

    返回：排名列表
    """
    # 复用工作量统计逻辑
    users_stmt = select(User).where(
        User.role.in_(["expert", "auditor", "admin", "super_admin"]),
        User.is_deleted == False,  # noqa: E712
    )
    users_result = await db.execute(users_stmt)
    users = users_result.scalars().all()

    # 只统计未删除项目（与 workload 同一口径）
    active_project_ids = select(AuditProject.id).where(
        AuditProject.is_deleted == False  # noqa: E712
    ).scalar_subquery()

    # 查询审核组成员关系（排除软删除的组员关系与软删除的项目）
    atm_stmt = (
        select(
            AuditTeamMember.member_id,
            AuditTeamMember.project_id,
        )
        .where(
            AuditTeamMember.is_deleted == False,  # noqa: E712
            AuditTeamMember.project_id.in_(active_project_ids),
        )
    )
    atm_result = await db.execute(atm_stmt)
    atm_rows = atm_result.all()

    # 查询不符合项开具情况（同样排除软删除项目）
    nc_stmt = (
        select(
            Nonconformity.created_by,
            func.count(Nonconformity.id).label("nc_count"),
        )
        .where(
            or_(
                Nonconformity.project_id.is_(None),
                Nonconformity.project_id.in_(active_project_ids),
            )
        )
        .group_by(Nonconformity.created_by)
    )
    nc_result = await db.execute(nc_stmt)
    nc_rows = nc_result.all()
    nc_dict = {row.created_by: row.nc_count for row in nc_rows}

    # 聚合数据
    user_projects = {}
    user_areas = {}

    for row in atm_rows:
        if row.member_id not in user_projects:
            user_projects[row.member_id] = set()
            user_areas[row.member_id] = set()
        user_projects[row.member_id].add(row.project_id)

    # 查询审核区域分配（排除软删除的计划项与软删除的项目）
    api_stmt = (
        select(
            AuditPlanItem.assigned_member_ids,
            AuditPlanItem.id,
        )
        .where(
            AuditPlanItem.is_deleted == False,  # noqa: E712
            AuditPlanItem.project_id.in_(active_project_ids),
        )
    )
    api_result = await db.execute(api_stmt)
    api_rows = api_result.all()

    for row in api_rows:
        if row.assigned_member_ids:
            for member_id in row.assigned_member_ids:
                if member_id in user_areas:
                    user_areas[member_id].add(row.id)

    # 构建排名数据
    ranking_data = []
    for user in users:
        project_count = len(user_projects.get(user.id, set()))
        area_count = len(user_areas.get(user.id, set()))
        nc_count = nc_dict.get(user.id, 0)

        ranking_data.append({
            "user_id": str(user.id),
            "name": user.full_name or user.username,
            "project_count": project_count,
            "area_count": area_count,
            "nc_count": nc_count,
        })

    # 根据指标排序
    sort_key_map = {
        "projects": "project_count",
        "areas": "area_count",
        "ncs": "nc_count",
    }

    sort_key = sort_key_map.get(metric, "project_count")
    ranking_data.sort(key=lambda x: x[sort_key], reverse=True)

    # 添加排名
    data = []
    for i, item in enumerate(ranking_data[:limit]):
        data.append({
            "rank": i + 1,
            **item,
        })

    return make_response(data=data)