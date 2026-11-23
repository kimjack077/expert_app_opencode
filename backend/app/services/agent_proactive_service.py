"""主动巡检服务（#6）。

把 Agent 从"你问我答"变成"我提前提醒你"：周期性扫描系统状态，发现风险信号后
生成 AgentNotification 推给相关审核员。带幂等去重，避免每轮巡检刷屏。

当前实现的信号：
- ``reaudit_due``：企业距上次审核超过阈值天数 → 提示安排复审。
- ``open_nonconformity``：不符合项超期未整改/关闭 → 提示跟进。
- ``stale_draft``：AI 草稿长期未确认 → 提示处理。

调度：由 main.py 的后台轮询循环按 PROACTIVE_SCAN_INTERVAL_SECONDS 调用。
通知落库，进程重启不丢（与 BackgroundTasks 不同）。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.agent_runtime import AgentNotification
from app.models.audit_project import AuditProject, Nonconformity
from app.models.enterprise import Enterprise
from app.models.evidence_agent import AiDraftRecord

logger = logging.getLogger(__name__)


async def _upsert_notification(
    db: AsyncSession,
    *,
    user_id: Optional[UUID],
    kind: str,
    dedupe_key: str,
    title: str,
    body: str,
    severity: str = "info",
    enterprise_id: Optional[UUID] = None,
    project_id: Optional[UUID] = None,
    payload: Optional[dict] = None,
) -> bool:
    """幂等写入提醒，返回是否新建。

    此前只按「同键未读」去重：用户一标记已读或忽略，下一轮巡检就会重新生成同一条提醒，
    铃铛永远清不掉。现在按同键最近一条判断：
    - 未读：跳过；
    - 已忽略：不再提醒；
    - 已读：7 天内不重复提醒，超过 7 天问题仍存在则再提醒一次。
    """
    latest = (await db.execute(
        select(AgentNotification.status, AgentNotification.created_at).where(
            AgentNotification.kind == kind,
            AgentNotification.dedupe_key == dedupe_key,
            AgentNotification.user_id.is_(user_id) if user_id is None else AgentNotification.user_id == user_id,
        ).order_by(AgentNotification.created_at.desc()).limit(1)
    )).first()
    if latest:
        status, created_at = latest
        if status in ("unread", "dismissed"):
            return False
        if status == "read" and created_at is not None:
            ts = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
            if ts > datetime.now(timezone.utc) - timedelta(days=7):
                return False
    db.add(AgentNotification(
        user_id=user_id, kind=kind, dedupe_key=dedupe_key, title=title, body=body,
        severity=severity, enterprise_id=enterprise_id, project_id=project_id,
        payload=payload or {},
    ))
    return True


class AgentProactiveService:
    async def scan(self, db: AsyncSession) -> dict[str, int]:
        """执行一轮主动巡检，返回各类新建通知数。"""
        now = datetime.now(timezone.utc)
        created = {"reaudit_due": 0, "open_nonconformity": 0, "stale_draft": 0}

        # 1) 企业到期需复审
        due_before = now - timedelta(days=settings.PROACTIVE_REAUDIT_DUE_DAYS)
        enterprises = (await db.execute(
            select(Enterprise).where(
                Enterprise.is_deleted == False,  # noqa: E712
                Enterprise.last_audit_date.isnot(None),
                Enterprise.last_audit_date < due_before,
            ).limit(200)
        )).scalars().all()
        for ent in enterprises:
            if await _upsert_notification(
                db, user_id=None, kind="reaudit_due", dedupe_key=str(ent.id),
                title=f"{ent.name} 已到复审周期",
                body=f"该企业上次审核为 {ent.last_audit_date}，已超过 {settings.PROACTIVE_REAUDIT_DUE_DAYS} 天，建议安排复审。",
                severity="warning", enterprise_id=ent.id,
            ):
                created["reaudit_due"] += 1

        # 2) 不符合项超期未关闭
        # 草稿（未经人工确认）与已驳回的 AI 草稿不属于正式 NC，不应提醒超期
        overdue_ncs = (await db.execute(
            select(Nonconformity, AuditProject)
            .join(AuditProject, Nonconformity.project_id == AuditProject.id)
            .where(
                Nonconformity.status.notin_(("verified", "closed", "cancelled", "draft", "rejected")),
                Nonconformity.due_date.isnot(None),
                Nonconformity.due_date < now,
                AuditProject.is_deleted == False,  # noqa: E712
            ).limit(200)
        )).all()
        nc_status_text = {
            "open": "待整改",
            "pending_rectification": "待整改",
            "corrected": "已整改·待验证",
            "pending_verification": "待验证",
        }
        for nc, project in overdue_ncs:
            clause = (nc.clause_no or "").strip()
            status_text = nc_status_text.get(nc.status or "", nc.status or "待整改")
            if await _upsert_notification(
                db, user_id=project.created_by, kind="open_nonconformity", dedupe_key=str(nc.id),
                title=f"不符合项超期未整改{'：条款 ' + clause if clause else ''}{('（' + nc.nc_no + '）') if getattr(nc, 'nc_no', None) else ''}",
                body=f"项目「{project.title}」的不符合项已超过整改期限（{nc.due_date}），当前状态：{status_text}。",
                severity="urgent", enterprise_id=project.enterprise_id, project_id=project.id,
                payload={"nc_id": str(nc.id), "tab": "nonconformities"},
            ):
                created["open_nonconformity"] += 1

        # 3) AI 草稿长期未确认（超过 3 天）
        stale_before = now - timedelta(days=3)
        stale = (await db.execute(
            select(AiDraftRecord.project_id, func.count(AiDraftRecord.id))
            .where(AiDraftRecord.status == "draft", AiDraftRecord.created_at < stale_before)
            .group_by(AiDraftRecord.project_id)
        )).all()
        for project_id, count in stale:
            project = await db.get(AuditProject, project_id)
            if not project:
                continue
            if await _upsert_notification(
                db, user_id=project.created_by, kind="stale_draft", dedupe_key=str(project_id),
                title=f"有 {count} 条 AI 草稿待确认",
                body=f"项目「{project.title}」有 {count} 条 AI 草稿超过 3 天未处理，会阻断资料包生成。",
                severity="info", project_id=project_id,
            ):
                created["stale_draft"] += 1

        await db.commit()
        total = sum(created.values())
        if total:
            logger.info("[Proactive] 新建提醒 %s", created)
        return created


agent_proactive_service = AgentProactiveService()
