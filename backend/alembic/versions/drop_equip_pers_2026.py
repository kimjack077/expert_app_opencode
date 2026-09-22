"""drop enterprise equipment/personnel tables (feature removed)

Revision ID: drop_equip_pers_2026
Revises: c7d8e9f0a1b2
Create Date: 2026-09-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "drop_equip_pers_2026"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("enterprise_personnel")
    op.drop_table("enterprise_equipment")


def downgrade():
    op.create_table(
        "enterprise_equipment",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enterprise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("manufacturer", sa.String(length=200), nullable=True),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["enterprise_id"], ["enterprises.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "enterprise_personnel",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enterprise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("position", sa.String(length=50), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("id_card", sa.String(length=20), nullable=True),
        sa.Column("education", sa.String(length=50), nullable=True),
        sa.Column("certificate", sa.String(length=100), nullable=True),
        sa.Column("cert_valid_until", sa.Date(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["enterprise_id"], ["enterprises.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
