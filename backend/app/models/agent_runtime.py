"""Agent 运行时相关模型：主动提醒。

主动性（#6）：后台巡检发现"企业到期需复审 / 存在未整改 NC"等信号时，
生成一条 AgentNotification 推送给相关审核员，把 Agent 从"你问我答"变成"我提前提醒你"。
"""

import uuid

from sqlalchemy import Column, DateTime, Index, JSON, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from ..database import Base


class AgentNotification(Base):
    """一条主动提醒卡片。"""

    __tablename__ = "agent_notifications"
    __table_args__ = (
        Index("ix_agent_notifications_user_status", "user_id", "status"),
        # 去重键：同一 (用户, 类型, 关联实体) 只保留一条未读，避免每轮巡检刷屏
        Index("ix_agent_notifications_dedupe", "user_id", "kind", "dedupe_key"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # 提醒的目标审核员；为空表示面向管理角色的广播
    user_id = Column(UUID(as_uuid=True), nullable=True)
    enterprise_id = Column(UUID(as_uuid=True), nullable=True)
    project_id = Column(UUID(as_uuid=True), nullable=True)
    kind = Column(
        String(40), nullable=False,
        comment="reaudit_due / open_nonconformity / stale_draft / plan_incomplete",
    )
    severity = Column(
        String(20), nullable=False, default="info", server_default="info",
        comment="info / warning / urgent",
    )
    title = Column(String(300), nullable=False)
    body = Column(Text)
    payload = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    # 幂等去重键（如 enterprise_id 或 nc_id 的字符串）
    dedupe_key = Column(String(200), nullable=False, default="", server_default="")
    status = Column(
        String(20), nullable=False, default="unread", server_default="unread",
        comment="unread / read / dismissed",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return f"<AgentNotification {self.kind} {self.status}>"
