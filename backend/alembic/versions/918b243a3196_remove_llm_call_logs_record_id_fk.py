"""remove llm_call_logs record_id fk

Revision ID: 918b243a3196
Revises: add_soft_delete_v2
Create Date: 2026-07-17 14:59:29.953775

移除 llm_call_logs.record_id 的外键约束，因为 record_id 是多态关联，
可能指向 task_item_records 或 inspection_record_items，不应强制外键到 inspection_records。
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '918b243a3196'
down_revision = 'add_soft_delete_v2'
branch_labels = None
depends_on = None

def upgrade():
    # 移除外键约束，record_id 为多态关联（task_item_records / inspection_record_items）
    op.drop_constraint(op.f('llm_call_logs_record_id_fkey'), 'llm_call_logs', type_='foreignkey')

def downgrade():
    op.create_foreign_key(op.f('llm_call_logs_record_id_fkey'), 'llm_call_logs', 'inspection_records', ['record_id'], ['id'])
