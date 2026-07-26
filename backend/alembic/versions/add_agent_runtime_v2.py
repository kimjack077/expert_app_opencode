"""agent runtime v2: feedback signal, long-term memory scope, proactive notifications

三处增量变更，全部可回滚、对既有数据无损：
1. ai_draft_records.was_edited —— 反馈闭环的编辑标注（#1）
2. agent_memories 增加 enterprise_id/project_id/scope —— 跨会话长期记忆作用域（#5）
3. 新增 agent_notifications 表 —— 主动提醒（#6）

Revision ID: add_agent_runtime_v2
Revises: add_ai_draft_provenance
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "add_agent_runtime_v2"
down_revision = "add_ai_draft_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) 反馈信号
    op.add_column(
        "ai_draft_records",
        sa.Column(
            "was_edited",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="确认时审核员是否改动了 AI 内容（用于采纳率统计）",
        ),
    )

    # 2) 长期记忆作用域
    op.add_column("agent_memories", sa.Column("enterprise_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("agent_memories", sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "agent_memories",
        sa.Column("scope", sa.String(length=20), nullable=False, server_default="user"),
    )
    op.create_index("ix_agent_memories_enterprise", "agent_memories", ["enterprise_id"])
    op.create_index("ix_agent_memories_project", "agent_memories", ["project_id"])

    # 3) 主动提醒表
    op.create_table(
        "agent_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("enterprise_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="info"),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("dedupe_key", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="unread"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_agent_notifications_user_status", "agent_notifications", ["user_id", "status"])
    op.create_index("ix_agent_notifications_dedupe", "agent_notifications", ["user_id", "kind", "dedupe_key"])


def downgrade() -> None:
    op.drop_index("ix_agent_notifications_dedupe", table_name="agent_notifications")
    op.drop_index("ix_agent_notifications_user_status", table_name="agent_notifications")
    op.drop_table("agent_notifications")

    op.drop_index("ix_agent_memories_project", table_name="agent_memories")
    op.drop_index("ix_agent_memories_enterprise", table_name="agent_memories")
    op.drop_column("agent_memories", "scope")
    op.drop_column("agent_memories", "project_id")
    op.drop_column("agent_memories", "enterprise_id")

    op.drop_column("ai_draft_records", "was_edited")
