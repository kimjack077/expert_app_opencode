"""add token revocation timestamp to users

Revision ID: f4c9a8d1b2e3
Revises: e7b23f8910cd
Create Date: 2026-09-19
"""

from alembic import op
import sqlalchemy as sa


revision = "f4c9a8d1b2e3"
down_revision = "e7b23f8910cd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "token_revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="令牌吊销时间；登出后使该时间点之前签发的 token 失效",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "token_revoked_at")
