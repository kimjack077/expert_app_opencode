"""add per-session token revocation storage

Revision ID: c7d8e9f0a1b2
Revises: f4c9a8d1b2e3
Create Date: 2026-09-19
"""

from alembic import op
import sqlalchemy as sa


revision = "c7d8e9f0a1b2"
down_revision = "f4c9a8d1b2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "revoked_sessions",
            sa.JSON(),
            nullable=False,
            server_default="[]",
            comment="已吊销的登录会话 ID；按设备/会话登出",
        ),
    )
    op.alter_column("users", "revoked_sessions", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "revoked_sessions")
