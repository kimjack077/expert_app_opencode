"""drop enterprise_instruments table

Revision ID: drop_enterprise_instruments
Revises: 918b243a3196
Create Date: 2026-07-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "drop_enterprise_instruments"
down_revision = "918b243a3196"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("enterprise_instruments")


def downgrade():
    op.create_table(
        "enterprise_instruments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enterprise_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("serial_no", sa.String(length=100), nullable=True),
        sa.Column("measure_range", sa.String(length=100), nullable=True),
        sa.Column("accuracy", sa.String(length=50), nullable=True),
        sa.Column("verification_method", sa.String(length=50), nullable=True),
        sa.Column("last_verified", sa.Date(), nullable=True),
        sa.Column("next_verified", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["enterprise_id"], ["enterprises.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
