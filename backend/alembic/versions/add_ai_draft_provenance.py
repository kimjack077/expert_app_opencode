"""add llm_call_log_id and widen prompt_version on ai_draft_records

审核结论具有法律效力，必须可复现：给 AI 草稿补上指向具体 LLM 调用的引用，
并放宽 prompt_version 长度以容纳「语义版本 + 提示词内容指纹」。

两处变更都是增量且可回滚的：
- 新增可空列，不影响既有行；
- prompt_version 由 VARCHAR(50) 放宽到 VARCHAR(100)（放宽不会截断数据）。

Revision ID: add_ai_draft_provenance
Revises: drop_enterprise_instruments
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "add_ai_draft_provenance"
down_revision = "drop_enterprise_instruments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_draft_records",
        sa.Column(
            "llm_call_log_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="产生该草稿的 LLM 调用（llm_call_logs.id，多态引用不加外键）",
        ),
    )
    op.alter_column(
        "ai_draft_records",
        "prompt_version",
        existing_type=sa.String(length=50),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
    # 按调用反查草稿（结论被质疑时的取证路径）
    op.create_index(
        "ix_ai_draft_records_llm_call_log",
        "ai_draft_records",
        ["llm_call_log_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_draft_records_llm_call_log", table_name="ai_draft_records")
    op.alter_column(
        "ai_draft_records",
        "prompt_version",
        existing_type=sa.String(length=100),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.drop_column("ai_draft_records", "llm_call_log_id")
