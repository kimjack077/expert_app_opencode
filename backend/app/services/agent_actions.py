"""服务端 Agent 动作注册表。

## 为什么需要它

改造前的写回链路是：LLM 自己产出 ``confirm_endpoint`` / ``confirm_method`` /
``confirm_payload``，前端拿到后直接发请求。这带来四个问题：

1. **模型决定写哪个接口**——安全边界落在客户端，而客户端守卫各不相同
   （web-admin 用正则、h5 用前缀校验、mobile-app 干脆禁用写回）。
2. **确认内容 ≠ 执行内容**——卡片展示的是 ``data`` 摘要，真正发送的是
   ``confirm_payload``，用户确认的和实际执行的可能不是一回事。
3. **每加一个写能力要改三个前端**——写回翻译逻辑在每个客户端各写一份。
4. **参数不受校验**——模型可以在 payload 里塞任意字段。

改造后：模型只能输出 ``action`` 名称 + 结构化参数。服务端按注册表校验参数、
重新鉴权、再执行。客户端只需要调用统一的确认接口，不需要知道任何业务端点。

## 契约

Agent 工具产出的提案形如::

    {"type": "action_proposal", "action": "apply_check_result",
     "status": "pending", "title": "...", "data": {...}}

提案由服务端持久化在 ``AgentMessage.extra_data``。用户确认时前端只回传
``message_id`` + ``action_index``，服务端取出**自己存的**提案执行——
客户端无法篡改要执行的内容。
"""

from __future__ import annotations

import random
from datetime import datetime, date, timedelta
from typing import Any, Awaitable, Callable, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.record import InspectionRecord, InspectionRecordItem
from app.models.task import InspectionTask, TaskItemRecord
from app.models.enterprise import Enterprise
from app.models.audit_project import AuditProject, AuditTeamMember, AuditPlanItem
from app.models.user import User
from app.utils.roles import ADMIN_ROLES

Handler = Callable[[AsyncSession, User, dict[str, Any]], Awaitable[dict[str, Any]]]

_REGISTRY: dict[str, Handler] = {}

VALID_CHECK_RESULTS = {"pass", "fail", "na"}
VALID_VERDICTS = {"pass", "partial_pass", "fail"}


def register(action: str) -> Callable[[Handler], Handler]:
    def decorator(fn: Handler) -> Handler:
        _REGISTRY[action] = fn
        return fn

    return decorator


def is_registered(action: str) -> bool:
    return action in _REGISTRY


def registered_actions() -> list[str]:
    return sorted(_REGISTRY)


async def execute_action(
    db: AsyncSession,
    user: User,
    action: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    """校验 → 鉴权 → 执行。未注册的动作一律拒绝（默认不放行）。"""
    handler = _REGISTRY.get(action)
    if handler is None:
        raise HTTPException(status_code=400, detail=f"不支持的 Agent 动作: {action}")
    return await handler(db, user, data or {})


# --------------------------------------------------------------------------
# 内部工具
# --------------------------------------------------------------------------


def _require(data: dict[str, Any], key: str) -> Any:
    value = data.get(key)
    if value in (None, ""):
        raise HTTPException(status_code=400, detail=f"缺少必要参数: {key}")
    return value


def _as_uuid(value: Any, field: str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=400, detail=f"{field} 不是合法的 ID")


async def _load_record_for_write(
    db: AsyncSession, user: User, record_id: Any
) -> InspectionRecord:
    """加载检查记录并校验归属。

    这里是写操作的授权关口：Agent 的上下文由客户端提供，
    不校验归属就会出现「让 Agent 写别人的记录」。
    """
    record = (
        await db.execute(
            select(InspectionRecord).where(
                InspectionRecord.id == _as_uuid(record_id, "record_id"),
                InspectionRecord.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="检查记录不存在")

    if user.role not in ADMIN_ROLES and str(record.inspector_id) != str(user.id):
        raise HTTPException(status_code=403, detail="无权修改他人的检查记录")
    return record


async def _authorize_task_item(
    db: AsyncSession, user: User, task_item: TaskItemRecord
) -> None:
    """任务流检查项的写授权：任务必须分配给当前用户。"""
    if user.role in ADMIN_ROLES:
        return

    task = await db.get(InspectionTask, task_item.task_id) if task_item.task_id else None
    if task is None:
        # 默认拒绝：父任务缺失时无法判断归属
        raise HTTPException(status_code=404, detail="检查项所属任务不存在")
    if str(task.assigned_to) != str(user.id):
        raise HTTPException(status_code=403, detail="无权修改他人的检查任务")


# --------------------------------------------------------------------------
# 动作实现
# --------------------------------------------------------------------------


@register("apply_check_result")
async def _apply_check_result(
    db: AsyncSession, user: User, data: dict[str, Any]
) -> dict[str, Any]:
    """回填单条检查项判定。

    系统里目前并存两套检查结果模型（见架构评估「三套记录模型」）：
    - 记录流：``InspectionRecordItem``（h5 / web-admin 的检查记录页）
    - 任务流：``TaskItemRecord``（mobile-app 的现场检查 / 快速检查页）

    能力层在这里统一吸收这个差异：按 item_id 先后尝试两种模型。
    这样三端可以共用同一个动作，客户端不需要知道自己在哪套表上，
    也不必像以前那样为了避开表结构不匹配而整体禁用写回。
    """
    result = _require(data, "result")
    if result not in VALID_CHECK_RESULTS:
        raise HTTPException(
            status_code=400, detail="判定结果必须是 pass / fail / na"
        )

    item_id = _as_uuid(_require(data, "item_id"), "item_id")

    # 1) 记录流
    item = await db.get(InspectionRecordItem, item_id)
    if item is not None:
        # 以检查项自身的 record_id 为准，不信任提案里带的 record_id
        await _load_record_for_write(db, user, item.record_id)

        item.result = result
        if data.get("problem_description") is not None:
            item.problem_description = str(data["problem_description"])
        if data.get("rectification_suggestion") is not None:
            item.rectification_suggestion = str(data["rectification_suggestion"])
        item.ai_generated = True

        await db.commit()
        await db.refresh(item)
        return {
            "applied": "apply_check_result",
            "flow": "record",
            "item_id": str(item.id),
            "record_id": str(item.record_id),
            "result": item.result,
        }

    # 2) 任务流
    task_item = await db.get(TaskItemRecord, item_id)
    if task_item is None:
        raise HTTPException(status_code=404, detail="检查项不存在")

    await _authorize_task_item(db, user, task_item)

    task_item.result = result
    if data.get("problem_description") is not None:
        task_item.result_text = str(data["problem_description"])
    if data.get("rectification_suggestion") is not None:
        task_item.llm_suggestion = str(data["rectification_suggestion"])
    task_item.recorded_by = user.id

    await db.commit()
    await db.refresh(task_item)
    return {
        "applied": "apply_check_result",
        "flow": "task",
        "item_id": str(task_item.id),
        "task_id": str(task_item.task_id) if task_item.task_id else None,
        "result": task_item.result,
    }


@register("apply_final_verdict")
async def _apply_final_verdict(
    db: AsyncSession, user: User, data: dict[str, Any]
) -> dict[str, Any]:
    verdict = _require(data, "verdict")
    if verdict not in VALID_VERDICTS:
        raise HTTPException(
            status_code=400, detail="最终判定必须是 pass / partial_pass / fail"
        )

    record = await _load_record_for_write(db, user, _require(data, "record_id"))
    record.overall_result = verdict
    if data.get("comment") is not None:
        record.remarks = str(data["comment"])

    await db.commit()
    await db.refresh(record)
    return {
        "applied": "apply_final_verdict",
        "record_id": str(record.id),
        "verdict": record.overall_result,
    }


@register("confirm_audit_drafts")
async def _confirm_audit_drafts(
    db: AsyncSession, user: User, data: dict[str, Any]
) -> dict[str, Any]:
    """确认正式审核 AI 草稿。

    复用 project_agent 的能力函数（内含行锁幂等闸 + 审核职责校验），
    不在这里另写一份业务逻辑。延迟导入以避免 router ↔ service 循环依赖。
    """
    from app.routers.project_agent import perform_draft_confirmation
    from app.schemas.project_agent import DraftConfirmRequest

    project_id = _as_uuid(_require(data, "project_id"), "project_id")
    session_id = _as_uuid(_require(data, "audit_session_id"), "audit_session_id")

    raw_ids = data.get("draft_ids") or []
    if not isinstance(raw_ids, list):
        raise HTTPException(status_code=400, detail="draft_ids 必须是数组")

    payload = DraftConfirmRequest(
        draft_ids=[str(_as_uuid(i, "draft_id")) for i in raw_ids],
        action=data.get("action") or "confirm",
        safe_only=bool(data.get("safe_only")),
        overrides=[],
    )

    result = await perform_draft_confirmation(db, project_id, session_id, payload, user)
    return {"applied": "confirm_audit_drafts", **result}


@register("add_team_member")
async def _add_team_member(
    db: AsyncSession, user: User, data: dict[str, Any]
) -> dict[str, Any]:
    """向审核项目添加审核组成员。"""
    from app.services.project_access_service import ensure_project_access
    from app.models.audit_project import AuditProject, AuditTeamMember

    project_id = _as_uuid(_require(data, "project_id"), "project_id")
    await ensure_project_access(db, project_id, user, require_manage=True)

    project = await db.get(AuditProject, project_id)
    if not project or project.is_deleted:
        raise HTTPException(status_code=404, detail="审核项目不存在")

    member_id_raw = data.get("member_id")
    target_user: Optional[User] = None
    if member_id_raw:
        target_user = await db.get(User, _as_uuid(member_id_raw, "member_id"))

    if not target_user and data.get("member_name"):
        member_name = str(data["member_name"]).strip()
        res = await db.execute(
            select(User).where(
                or_(User.full_name == member_name, User.username == member_name),
                User.is_deleted == False,
            )
        )
        target_user = res.scalar_one_or_none()

    if not target_user:
        raise HTTPException(status_code=404, detail="未找到指定的审核员用户")

    # 检查是否已在审核组中
    existing = await db.execute(
        select(AuditTeamMember).where(
            AuditTeamMember.project_id == project_id,
            AuditTeamMember.member_id == target_user.id,
            AuditTeamMember.is_deleted == False,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"审核员 {target_user.full_name or target_user.username} 已在当前审核组中",
        )

    role = str(data.get("role") or "member")
    responsible_systems = data.get("responsible_systems")
    if not responsible_systems:
        responsible_systems = project.certification_systems or []
    elif not isinstance(responsible_systems, list):
        responsible_systems = [str(responsible_systems)]

    db_member = AuditTeamMember(
        project_id=project_id,
        member_id=target_user.id,
        role=role,
        responsible_systems=responsible_systems,
        qualification_codes=target_user.qualified_industry_codes or [],
        registration_no=target_user.auditor_registration_no,
        registration_level=target_user.auditor_level,
        assigned_areas=data.get("assigned_areas") or [],
        assigned_clauses=data.get("assigned_clauses") or [],
        status="assigned",
    )
    db.add(db_member)
    await db.commit()
    await db.refresh(db_member)

    return {
        "applied": "add_team_member",
        "team_member_id": str(db_member.id),
        "project_id": str(project_id),
        "member_name": target_user.full_name or target_user.username,
        "role": db_member.role,
        "responsible_systems": db_member.responsible_systems,
    }


@register("create_audit_plan")
async def _action_create_audit_plan(
    db: AsyncSession,
    user: User,
    data: dict[str, Any],
) -> dict[str, Any]:
    project_id = _as_uuid(_require(data, "project_id"), "project_id")
    project = await db.get(AuditProject, project_id)
    if not project or project.is_deleted:
        raise HTTPException(status_code=404, detail="审核项目不存在")

    raw_items = data.get("plan_items") or []
    if not raw_items or not isinstance(raw_items, list):
        raise HTTPException(status_code=400, detail="缺少有效的审核计划项列表")

    # 获取当前审核组成员与系统用户映射
    team_members_res = await db.execute(
        select(AuditTeamMember, User)
        .join(User, AuditTeamMember.member_id == User.id)
        .where(
            AuditTeamMember.project_id == project_id,
            AuditTeamMember.is_deleted == False,
            User.is_deleted == False,
        )
    )
    name_to_user_id: dict[str, UUID] = {}
    for tm, u in team_members_res.all():
        if u.full_name:
            name_to_user_id[u.full_name] = u.id
        if u.username:
            name_to_user_id[u.username] = u.id

    enterprise = await db.get(Enterprise, project.enterprise_id) if project.enterprise_id else None
    base_date = project.scheduled_start or date.today()

    created_items = []
    for idx, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue

        raw_date = item.get("plan_date")
        plan_date: date = base_date
        if raw_date:
            if isinstance(raw_date, date):
                plan_date = raw_date
            elif isinstance(raw_date, str):
                d_str = raw_date.strip()
                try:
                    plan_date = datetime.strptime(d_str[:10], "%Y-%m-%d").date()
                except Exception:
                    if "1" in d_str or "一" in d_str:
                        plan_date = base_date
                    elif "2" in d_str or "二" in d_str:
                        plan_date = base_date + timedelta(days=1)
                    elif "3" in d_str or "三" in d_str:
                        plan_date = base_date + timedelta(days=2)
                    elif "4" in d_str or "四" in d_str:
                        plan_date = base_date + timedelta(days=3)
                    elif "5" in d_str or "五" in d_str:
                        plan_date = base_date + timedelta(days=4)
                    else:
                        plan_date = base_date

        time_start = str(item.get("time_start") or "08:30")
        time_end = str(item.get("time_end") or "12:00")
        area_name = str(item.get("area_name") or f"审核区域-{idx+1}").strip()
        area_type = str(item.get("area_type") or "department")
        group_no = str(item.get("group_no") or "A")

        assigned_member_ids: list[UUID] = []
        raw_assigned = item.get("assigned_member_ids") or []
        for mid in raw_assigned:
            try:
                assigned_member_ids.append(UUID(str(mid)))
            except Exception:
                pass

        raw_names = item.get("assigned_member_names") or []
        if isinstance(raw_names, str):
            raw_names = [raw_names]
        for name in raw_names:
            name_clean = str(name).strip()
            if name_clean in name_to_user_id and name_to_user_id[name_clean] not in assigned_member_ids:
                assigned_member_ids.append(name_to_user_id[name_clean])

        if not assigned_member_ids:
            if name_to_user_id:
                assigned_member_ids.append(next(iter(name_to_user_id.values())))
            else:
                assigned_member_ids.append(user.id)

        systems = item.get("certification_systems") or project.certification_systems or []
        if not isinstance(systems, list):
            systems = [str(systems)]

        clauses = item.get("clauses") or []
        if not isinstance(clauses, list):
            clauses = [str(clauses)]

        activity_type = str(item.get("activity_type") or "normal")
        remarks = str(item.get("remarks") or "")

        random_suffix = "".join([str(random.randint(0, 9)) for _ in range(6)])
        task_no = f"TASK-{datetime.now().strftime('%Y%m%d')}-{random_suffix}"
        task_title = f"{project.title} - {area_name} - {plan_date}"

        inspection_task = InspectionTask(
            task_no=task_no,
            title=task_title,
            template_id=None,
            assigned_to=assigned_member_ids[0] if assigned_member_ids else user.id,
            assigned_by=user.id,
            target_name=enterprise.name if enterprise else project.title,
            target_address=enterprise.address if enterprise else None,
            scheduled_at=datetime.combine(plan_date, datetime.min.time()),
            status="pending",
        )
        db.add(inspection_task)
        await db.flush()

        db_plan_item = AuditPlanItem(
            project_id=project_id,
            inspection_task_id=inspection_task.id,
            plan_date=plan_date,
            time_start=time_start,
            time_end=time_end,
            group_no=group_no,
            area_name=area_name,
            area_type=area_type,
            assigned_member_ids=assigned_member_ids,
            certification_systems=systems,
            clauses=clauses,
            activity_type=activity_type,
            status="pending",
            remarks=remarks,
        )
        db.add(db_plan_item)
        await db.flush()

        created_items.append({
            "id": str(db_plan_item.id),
            "area_name": area_name,
            "plan_date": str(plan_date),
            "time_start": time_start,
            "time_end": time_end,
            "certification_systems": systems,
            "clauses": clauses,
        })

    await db.commit()

    return {
        "applied": "create_audit_plan",
        "project_id": str(project_id),
        "created_count": len(created_items),
        "plan_items": created_items,
    }


