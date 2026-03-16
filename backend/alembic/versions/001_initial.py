"""Initial migration

Revision ID: 001
Create Date: 2024-02-23

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), unique=True),
        sa.Column("description", sa.Text),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(50), unique=True, nullable=False),
        sa.Column("email", sa.String(100), unique=True),
        sa.Column("phone", sa.String(20)),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(100)),
        sa.Column("role", sa.String(20), nullable=False, server_default="expert"),
        sa.Column(
            "org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id")
        ),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "standard_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50)),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("standard_categories.id"),
        ),
        sa.Column("level", sa.Integer, nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("description", sa.Text),
        sa.Column("legal_basis", sa.Text),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )

    op.create_table(
        "check_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("standard_categories.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("check_method", sa.Text),
        sa.Column("legal_basis", sa.Text),
        sa.Column("standard_ref", sa.String(200)),
        sa.Column("result_type", sa.String(20), server_default="yes_no"),
        sa.Column("result_options", postgresql.JSONB),
        sa.Column("is_required", sa.Boolean, server_default="true"),
        sa.Column("risk_level", sa.String(20), server_default="medium"),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("tags", postgresql.ARRAY(sa.Text)),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )

    op.create_table(
        "inspection_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), unique=True),
        sa.Column("description", sa.Text),
        sa.Column("category", sa.String(100)),
        sa.Column("version", sa.String(20), server_default="1.0"),
        sa.Column("is_published", sa.Boolean, server_default="false"),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )

    op.create_table(
        "template_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inspection_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "check_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("check_items.id"),
        ),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("is_required", sa.Boolean, server_default="true"),
        sa.Column("custom_title", sa.String(500)),
    )
    op.create_unique_constraint(
        "uq_template_items", "template_items", ["template_id", "check_item_id"]
    )

    op.create_table(
        "inspection_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_no", sa.String(50), unique=True, nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inspection_templates.id"),
        ),
        sa.Column(
            "assigned_to", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")
        ),
        sa.Column(
            "assigned_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")
        ),
        sa.Column("target_name", sa.String(200)),
        sa.Column("target_address", sa.String(500)),
        sa.Column("target_contact", sa.String(100)),
        sa.Column("target_phone", sa.String(20)),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("remarks", sa.Text),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )

    op.create_table(
        "inspection_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inspection_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "check_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("check_items.id"),
        ),
        sa.Column("result", sa.String(20)),
        sa.Column("result_score", sa.String(10)),
        sa.Column("result_text", sa.Text),
        sa.Column("inspector_note", sa.Text),
        sa.Column("llm_suggestion", sa.Text),
        sa.Column("llm_basis", sa.Text),
        sa.Column(
            "recorded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")
        ),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )

    op.create_table(
        "media_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inspection_tasks.id"),
        ),
        sa.Column(
            "record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inspection_records.id"),
        ),
        sa.Column("file_type", sa.String(20), server_default="image"),
        sa.Column("original_name", sa.String(255)),
        sa.Column("stored_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_size", sa.BigInteger),
        sa.Column("mime_type", sa.String(100)),
        sa.Column("thumbnail_path", sa.String(500)),
        sa.Column("lat", sa.String(50)),
        sa.Column("lng", sa.String(50)),
        sa.Column(
            "uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")
        ),
        sa.Column(
            "uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("username", sa.String(50)),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50)),
        sa.Column("resource_id", sa.String(100)),
        sa.Column("detail", postgresql.JSONB),
        sa.Column("ip_address", sa.String(50)),
        sa.Column("user_agent", sa.Text),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_audit_logs_user", "audit_logs", ["user_id", sa.text("created_at DESC")]
    )
    op.create_index(
        "ix_audit_logs_action", "audit_logs", ["action", sa.text("created_at DESC")]
    )

    op.create_table(
        "llm_call_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inspection_tasks.id"),
        ),
        sa.Column(
            "record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inspection_records.id"),
        ),
        sa.Column("call_type", sa.String(20), nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("response", sa.Text),
        sa.Column("model", sa.String(100)),
        sa.Column("tokens_used", sa.Integer),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("is_success", sa.String(10), server_default="true"),
        sa.Column("error_msg", sa.Text),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("llm_call_logs")
    op.drop_table("audit_logs")
    op.drop_table("media_files")
    op.drop_table("inspection_records")
    op.drop_table("inspection_tasks")
    op.drop_table("template_items")
    op.drop_table("inspection_templates")
    op.drop_table("check_items")
    op.drop_table("standard_categories")
    op.drop_table("users")
    op.drop_table("organizations")
