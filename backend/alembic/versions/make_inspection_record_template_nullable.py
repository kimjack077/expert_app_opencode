"""make inspection_record template_id nullable

Revision ID: make_inspection_record_template_nullable
Revises: fcbf0d3dcfd6
Create Date: 2026-07-16 18:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'make_record_tmpl_nullable'
down_revision = 'a49ad7e0875f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 将 inspection_records.template_id 改为 nullable，便于删除模板时解除引用
    op.alter_column(
        'inspection_records',
        'template_id',
        existing_type=sa.UUID(as_uuid=True),
        nullable=True,
        existing_comment='使用的检查模板 ID（模板删除后置 NULL，历史数据由 template_snapshot 保留）',
    )


def downgrade() -> None:
    op.alter_column(
        'inspection_records',
        'template_id',
        existing_type=sa.UUID(as_uuid=True),
        nullable=False,
    )
