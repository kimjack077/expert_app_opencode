"""increase_result_field_length

Revision ID: db5085d66adb
Revises: 38807a515b7d
Create Date: 2026-03-25 16:29:46.425103

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'db5085d66adb'
down_revision = '38807a515b7d'
branch_labels = None
depends_on = None

def upgrade():
    # 扩展 task_item_records.result 字段长度以支持 pending_rectification
    op.alter_column('task_item_records', 'result',
               existing_type=sa.VARCHAR(length=20),
               type_=sa.String(length=30),
               comment='检查结果：pass/fail/pending_rectification 等',
               existing_comment='检查结果：pass/fail 等',
               existing_nullable=True)

def downgrade():
    op.alter_column('task_item_records', 'result',
               existing_type=sa.String(length=30),
               type_=sa.VARCHAR(length=20),
               comment='检查结果：pass/fail 等',
               existing_comment='检查结果：pass/fail/pending_rectification 等',
               existing_nullable=True)