"""add inspection_task_id to audit_plan_items

Revision ID: 38807a515b7d
Revises: b42d55a37961
Create Date: 2026-03-23 21:28:05.017905

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '38807a515b7d'
down_revision = 'b42d55a37961'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('audit_plan_items', sa.Column('inspection_task_id', sa.UUID(), nullable=True, comment='关联的检查任务 ID（创建计划项时自动生成）'))
    op.create_foreign_key('audit_plan_items_inspection_task_id_fkey', 'audit_plan_items', 'inspection_tasks', ['inspection_task_id'], ['id'], ondelete='SET NULL')

def downgrade():
    op.drop_constraint('audit_plan_items_inspection_task_id_fkey', 'audit_plan_items', type_='foreignkey')
    op.drop_column('audit_plan_items', 'inspection_task_id')
