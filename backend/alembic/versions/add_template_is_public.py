"""add is_public field to template

Revision ID: add_template_is_public
Revises: fcbf0d3dcfd6
Create Date: 2026-03-15 12:00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_template_is_public'
down_revision = 'fcbf0d3dcfd6'
branch_labels = None
depends_on = None

def upgrade():
    # 添加 is_public 字段
    op.add_column('inspection_templates', sa.Column('is_public', sa.Boolean, nullable=True, default=False, comment='是否公共模板'))
    # 设置默认值为 False
    op.execute("UPDATE inspection_templates SET is_public = FALSE WHERE is_public IS NULL")
    # 设置管理员创建的已发布模板为公共模板
    op.execute("""
        UPDATE inspection_templates
        SET is_public = TRUE
        WHERE is_published = TRUE
        AND created_by IN (SELECT id FROM users WHERE role IN ('admin', 'super_admin'))
    """)

def downgrade():
    op.drop_column('inspection_templates', 'is_public')