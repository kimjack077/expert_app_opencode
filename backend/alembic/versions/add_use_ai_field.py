"""add use_ai field

Revision ID: add_use_ai_field
Revises: add_check_type_support
Create Date: 2026-03-08

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_use_ai_field'
down_revision = 'add_check_type_support'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('template_items', sa.Column('use_ai', sa.Boolean, nullable=True, default=False, comment='是否使用AI'))
    op.execute("ALTER TABLE template_items ALTER COLUMN use_ai SET DEFAULT False")


def downgrade():
    op.drop_column('template_items', 'use_ai')
