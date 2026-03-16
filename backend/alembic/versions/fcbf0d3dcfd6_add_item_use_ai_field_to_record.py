"""add item_use_ai_field to record

Revision ID: fcbf0d3dcfd6
Revises: add_use_ai_field
Create Date: 2026-03-09 11:15:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'fcbf0d3dcfd6'
down_revision = 'add_use_ai_field'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('inspection_record_items', sa.Column('item_use_ai', sa.Boolean, nullable=True, default=False, comment='快照：是否使用AI'))
    op.execute("ALTER TABLE inspection_record_items ALTER COLUMN item_use_ai SET DEFAULT False")

def downgrade():
    op.drop_column('inspection_record_items', 'item_use_ai')
