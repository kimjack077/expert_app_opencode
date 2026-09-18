from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.task import InspectionTask, TaskItemRecord
from app.models.audit import AuditLog, LLMCallLog
from app.models.enterprise import Enterprise
from app.schemas import ApiResponse
from app.utils.security import get_current_user, get_current_admin_user
from app.utils.item_stats import classify_result

router = APIRouter()


def _summarize_task_records(record_rows) -> dict:
    """按统一口径汇总检查项结果分布（工作台专用）。

    与「检查记录详情」「检查报告」共用 ``app.utils.item_stats.classify_result``，
    避免同一批数据在工作台与详情页给出不同的「不适用」数字——
    历史上工作台只认 ``("na","not_applicable")``、详情只认 ``"na"``，两处对不上。

    ``filled`` 定义为 pass + fail + na，保证
    「合格 + 不合格 + 不适用 + 未填报 = 总检查项」在页面上闭合
    （``observe`` / ``pending_rectification`` 属中间态，不计入已填报）。
    """
    stats = {"total": 0, "pass": 0, "fail": 0, "na": 0, "filled": 0}
    for result, count in record_rows:
        stats["total"] += count
        bucket = classify_result(result)
        if bucket:
            stats[bucket] += count
            stats["filled"] += count
    return stats


def make_response(data=None, code=200, message="success"):
    return ApiResponse(
        code=code, message=message, data=data, timestamp=datetime.now(timezone.utc)
    )


@router.get("/dashboard", response_model=ApiResponse)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # BUG-30：原实现拆成 8~11 条串行 COUNT 查询，叠加远程库 RTT 后接口耗时 7~20s。
    # 改为 GROUP BY 聚合，把任务状态与填报结果各压缩为 1 条查询（语义完全一致）。
    if current_user.role == "expert":
        task_rows = (
            await db.execute(
                select(InspectionTask.status, func.count(InspectionTask.id))
                .where(
                    InspectionTask.assigned_to == current_user.id,
                    InspectionTask.is_deleted == False,  # noqa: E712
                )
                .group_by(InspectionTask.status)
            )
        ).all()
        task_counts = {s: c for s, c in task_rows}
        total_tasks = sum(task_counts.values())
        completed_tasks = task_counts.get("completed", 0)
        in_progress_tasks = task_counts.get("in_progress", 0)
        pending_tasks = task_counts.get("pending", 0)
        cancelled_tasks = task_counts.get("cancelled", 0)

        record_rows = (
            await db.execute(
                select(TaskItemRecord.result, func.count(TaskItemRecord.id))
                .join(InspectionTask, TaskItemRecord.task_id == InspectionTask.id)
                .where(
                    InspectionTask.assigned_to == current_user.id,
                    InspectionTask.is_deleted == False,  # noqa: E712
                )
                .group_by(TaskItemRecord.result)
            )
        ).all()
        _s = _summarize_task_records(record_rows)
        total_records = _s["total"]
        filled_records = _s["filled"]
        compliant_records = _s["pass"]
        non_compliant_records = _s["fail"]
        not_applicable_records = _s["na"]
    else:
        task_rows = (
            await db.execute(
                select(InspectionTask.status, func.count(InspectionTask.id))
                .where(InspectionTask.is_deleted == False)  # noqa: E712
                .group_by(InspectionTask.status)
            )
        ).all()
        task_counts = {s: c for s, c in task_rows}
        total_tasks = sum(task_counts.values())
        completed_tasks = task_counts.get("completed", 0)
        in_progress_tasks = task_counts.get("in_progress", 0)
        pending_tasks = task_counts.get("pending", 0)
        cancelled_tasks = task_counts.get("cancelled", 0)

        record_rows = (
            await db.execute(
                select(TaskItemRecord.result, func.count(TaskItemRecord.id))
                .join(InspectionTask, TaskItemRecord.task_id == InspectionTask.id)
                .where(InspectionTask.is_deleted == False)  # noqa: E712
                .group_by(TaskItemRecord.result)
            )
        ).all()
        _s = _summarize_task_records(record_rows)
        total_records = _s["total"]
        filled_records = _s["filled"]
        compliant_records = _s["pass"]
        non_compliant_records = _s["fail"]
        not_applicable_records = _s["na"]

    # 用户/企业总数只统计未删除记录，与列表页口径一致（单次复合标量查询，减少 1 次网络往返）
    counts_row = (
        await db.execute(
            select(
                select(func.count(User.id))
                .where(User.is_deleted == False)  # noqa: E712
                .scalar_subquery(),
                select(func.count(Enterprise.id))
                .where(Enterprise.is_deleted == False)  # noqa: E712
                .scalar_subquery(),
            )
        )
    ).first()
    total_users = counts_row[0] or 0 if counts_row else 0
    total_enterprises = counts_row[1] or 0 if counts_row else 0

    return make_response(
        data={
            "tasks": {
                "total": total_tasks,
                "completed": completed_tasks,
                "in_progress": in_progress_tasks,
                "pending": pending_tasks,
                "cancelled": cancelled_tasks,
                "completion_rate": round(completed_tasks / total_tasks * 100, 2)
                if total_tasks > 0
                else 0,
            },
            "inspections": {
                # total = 全部检查项；filled = 已填报项；两者相减即为未填报，
                # 让「合格 + 不合格 + 不适用 + 未填报 = 总检查项」在页面上闭合
                "total": total_records,
                "filled": filled_records,
                "not_filled": max(total_records - filled_records, 0),
                "compliant": compliant_records,
                "non_compliant": non_compliant_records,
                "not_applicable": not_applicable_records,
                # 达标率口径：合格 ÷（总项 - 不适用项），与 item_stats.compliance_rate 及报告侧统一
                "compliance_rate": round(
                    compliant_records / (total_records - not_applicable_records) * 100,
                    2,
                )
                if (total_records - not_applicable_records) > 0
                else 0,
            },
            "users": {
                "total": total_users,
            },
            "enterprises": {
                "total": total_enterprises,
            },
        }
    )


@router.get("/audit-logs", response_model=ApiResponse)
async def get_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    )
    logs = result.scalars().all()

    total = (await db.execute(select(func.count(AuditLog.id)))).scalar()

    return make_response(
        data={
            "items": [
                {
                    "id": log.id,
                    "user_id": str(log.user_id) if log.user_id else None,
                    "username": log.username,
                    "action": log.action,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "detail": log.detail,
                    "ip_address": log.ip_address,
                    "created_at": log.created_at.isoformat()
                    if log.created_at
                    else None,
                }
                for log in logs
            ],
            "total": total,
        }
    )


@router.get("/llm-logs", response_model=ApiResponse)
async def get_llm_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    result = await db.execute(
        select(LLMCallLog)
        .order_by(LLMCallLog.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    logs = result.scalars().all()

    total = (await db.execute(select(func.count(LLMCallLog.id)))).scalar()

    return make_response(
        data={
            "items": [
                {
                    "id": str(log.id),
                    "user_id": str(log.user_id) if log.user_id else None,
                    "task_id": str(log.task_id) if log.task_id else None,
                    "call_type": log.call_type,
                    "model": log.model,
                    "tokens_used": log.tokens_used,
                    "duration_ms": log.duration_ms,
                    "is_success": log.is_success,
                    "error_msg": log.error_msg,
                    "created_at": log.created_at.isoformat()
                    if log.created_at
                    else None,
                }
                for log in logs
            ],
            "total": total,
        }
    )


@router.get("/trends", response_model=ApiResponse)
async def get_trends(
    start_date: str = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        start = datetime.now(timezone.utc) - timedelta(days=30)
    
    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    else:
        end = datetime.now(timezone.utc) + timedelta(days=1)
    
    # BUG-30：原实现逐日循环内执行 2~3 条查询（30 天 = 60+ 次串行往返，实测 ~60s）。
    # 改为「任务按日 GROUP BY」+「记录按日 GROUP BY」两条聚合查询，再在内存填充日期序列，
    # 语义与原实现严格一致（记录仍限定为「任务创建当天填报」）。
    if current_user.role == "expert":
        task_rows = (
            await db.execute(
                select(
                    func.date(InspectionTask.created_at).label("d"),
                    func.count(InspectionTask.id),
                )
                .where(
                    InspectionTask.assigned_to == current_user.id,
                    InspectionTask.is_deleted == False,  # noqa: E712
                    InspectionTask.created_at >= start,
                    InspectionTask.created_at < end,
                )
                .group_by(func.date(InspectionTask.created_at))
            )
        ).all()
        rec_rows = (
            await db.execute(
                select(
                    func.date(TaskItemRecord.recorded_at).label("d"),
                    TaskItemRecord.result,
                    func.count(TaskItemRecord.id),
                )
                .select_from(TaskItemRecord)
                .join(InspectionTask, TaskItemRecord.task_id == InspectionTask.id)
                .where(
                    InspectionTask.assigned_to == current_user.id,
                    InspectionTask.is_deleted == False,  # noqa: E712
                    InspectionTask.created_at >= start,
                    InspectionTask.created_at < end,
                    TaskItemRecord.result.in_(["pass", "fail"]),
                    func.date(TaskItemRecord.recorded_at)
                    == func.date(InspectionTask.created_at),
                )
                .group_by(func.date(TaskItemRecord.recorded_at), TaskItemRecord.result)
            )
        ).all()
    else:
        task_rows = (
            await db.execute(
                select(
                    func.date(InspectionTask.created_at).label("d"),
                    func.count(InspectionTask.id),
                )
                .where(
                    InspectionTask.is_deleted == False,  # noqa: E712
                    InspectionTask.created_at >= start,
                    InspectionTask.created_at < end,
                )
                .group_by(func.date(InspectionTask.created_at))
            )
        ).all()
        rec_rows = (
            await db.execute(
                select(
                    func.date(TaskItemRecord.recorded_at).label("d"),
                    TaskItemRecord.result,
                    func.count(TaskItemRecord.id),
                )
                .select_from(TaskItemRecord)
                .join(InspectionTask, TaskItemRecord.task_id == InspectionTask.id)
                .where(
                    InspectionTask.is_deleted == False,  # noqa: E712
                    TaskItemRecord.result.in_(["pass", "fail"]),
                    TaskItemRecord.recorded_at >= start,
                    TaskItemRecord.recorded_at < end,
                )
                .group_by(func.date(TaskItemRecord.recorded_at), TaskItemRecord.result)
            )
        ).all()

    def _day_key(value) -> str:
        return value.strftime("%Y-%m-%d") if hasattr(value, "strftime") else str(value)

    task_map = {_day_key(d): c for d, c in task_rows}
    pass_map: dict = {}
    fail_map: dict = {}
    for d, result, cnt in rec_rows:
        key = _day_key(d)
        # 判定归类统一走 classify_result：旧实现只认字面量 "pass"/"fail"，
        # 会漏掉 compliant / qualified / non_compliant / unqualified 等历史与外部集成写法，
        # 导致趋势图与工作台汇总数字对不上。
        bucket = classify_result(result)
        if bucket == "pass":
            pass_map[key] = cnt
        elif bucket == "fail":
            fail_map[key] = cnt

    inspection_trend = []
    compliance_trend = []
    current = start
    while current < end:
        key = current.strftime("%Y-%m-%d")
        compliant = pass_map.get(key, 0)
        non_compliant = fail_map.get(key, 0)
        total_items = compliant + non_compliant
        compliance_rate = round(compliant / total_items * 100, 2) if total_items > 0 else 0

        inspection_trend.append({"date": key, "count": task_map.get(key, 0)})
        compliance_trend.append({
            "date": key,
            "rate": compliance_rate,
            "compliant": compliant,
            "non_compliant": non_compliant,
        })
        current += timedelta(days=1)
    
    return make_response(
        data={
            "inspection_trend": inspection_trend,
            "compliance_trend": compliance_trend,
        }
    )


@router.get("/enterprise-risk", response_model=ApiResponse)
async def get_enterprise_risk(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 风险分布只统计未删除企业，与「企业总库」列表口径一致
    #（曾有 93 家软删除企业把高风险 2 统计成 7、中风险 6 统计成 94）
    active = Enterprise.is_deleted == False  # noqa: E712
    high_risk = (
        await db.execute(
            select(func.count(Enterprise.id)).where(
                active, Enterprise.risk_level == "A"
            )
        )
    ).scalar() or 0

    medium_risk = (
        await db.execute(
            select(func.count(Enterprise.id)).where(
                active, Enterprise.risk_level == "B"
            )
        )
    ).scalar() or 0

    low_risk = (
        await db.execute(
            select(func.count(Enterprise.id)).where(
                active,
                Enterprise.risk_level.in_(["C", "D", None]),
            )
        )
    ).scalar() or 0
    
    return make_response(
        data={
            "high": high_risk,
            "medium": medium_risk,
            "low": low_risk,
        }
    )


@router.get("/export", response_model=ApiResponse)
async def export_data(
    start_date: str = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        start = datetime.now(timezone.utc) - timedelta(days=30)
    
    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    else:
        end = datetime.now(timezone.utc) + timedelta(days=1)
    
    # 状态一律导出中文，避免把 pending / in_progress 这类枚举写进交付文件
    status_labels = {
        "pending": "待开始",
        "in_progress": "进行中",
        "completed": "已完成",
        "cancelled": "已取消",
    }

    if current_user.role == "expert":
        tasks_query = await db.execute(
            select(InspectionTask).where(
                InspectionTask.assigned_to == current_user.id,
                InspectionTask.is_deleted == False,  # noqa: E712
                InspectionTask.created_at >= start,
                InspectionTask.created_at < end,
            ).order_by(InspectionTask.created_at.desc())
        )
    else:
        tasks_query = await db.execute(
            select(InspectionTask).where(
                InspectionTask.is_deleted == False,  # noqa: E712
                InspectionTask.created_at >= start,
                InspectionTask.created_at < end,
            ).order_by(InspectionTask.created_at.desc())
        )
    
    tasks = tasks_query.scalars().all()
    
    export_data = []
    for task in tasks:
        records_query = await db.execute(
            select(TaskItemRecord).where(TaskItemRecord.task_id == task.id)
        )
        records = records_query.scalars().all()
        
        # 导出报表的合格/不合格计数必须与详情页同源，
        # 不能只认字面量 "pass"/"fail"。
        compliant = sum(1 for r in records if classify_result(r.result) == "pass")
        non_compliant = sum(1 for r in records if classify_result(r.result) == "fail")
        
        export_data.append({
            "task_id": str(task.id),
            "task_no": task.task_no,
            "title": task.title,
            "target_name": task.target_name,
            "status": status_labels.get(task.status, task.status),
            "status_code": task.status,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "compliant_items": compliant,
            "non_compliant_items": non_compliant,
        })
    
    return make_response(
        data={
            "items": export_data,
            "export_time": datetime.now(timezone.utc).isoformat(),
        }
    )
