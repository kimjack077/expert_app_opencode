"""add soft delete columns v2

Revision ID: add_soft_delete_v2
Revises: add_soft_delete_cols
Create Date: 2026-07-16 19:30:00.000000

为以下表添加 is_deleted (Boolean) 和 deleted_at (DateTime) 字段，支持软删除：
- audit_projects
- audit_team_members
- audit_plan_items
- inspection_records
- template_items
- enterprise_qualifications
- media_files
- project_artifacts
- project_documents

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_soft_delete_v2'
down_revision = 'add_soft_delete_cols'
branch_labels = None
depends_on = None


TABLES = [
    "audit_projects",
    "audit_team_members",
    "audit_plan_items",
    "inspection_records",
    "template_items",
    "enterprise_qualifications",
    "media_files",
    "project_artifacts",
    "project_documents",
]


def upgrade() -> None:
    for tbl in TABLES:
        op.add_column(
            tbl,
            sa.Column(
                "is_deleted",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
                comment="是否软删除",
            ),
        )
        op.add_column(
            tbl,
            sa.Column(
                "deleted_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="软删除时间",
            ),
        )
        op.create_index(
            f"ix_{tbl}_is_deleted",
            tbl,
            ["is_deleted"],
        )


def downgrade() -> None:
    for tbl in TABLES:
        op.drop_index(f"ix_{tbl}_is_deleted", table_name=tbl)
        op.drop_column(tbl, "deleted_at")
        op.drop_column(tbl, "is_deleted")
