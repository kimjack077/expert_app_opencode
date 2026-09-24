"""add_performance_indexes_for_template_items

Revision ID: 35f52a3d6ee3
Revises: drop_equip_pers_2026
Create Date: 2026-09-24 17:45:49.709787

添加性能优化索引：
1. template_items(template_id) WHERE is_deleted = false
   - 加速按模板查询检查项
2. template_items(parent_id) WHERE is_deleted = false AND parent_id IS NOT NULL
   - 加速父子关系查询
3. template_items(template_id, parent_id) WHERE is_deleted = false
   - 加速树形结构查询

预期效果：
- 模板列表查询从 9.3秒 降为 < 1秒
- 检查记录详情查询速度提升 5-10倍
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '35f52a3d6ee3'
down_revision = 'drop_equip_pers_2026'
branch_labels = None
depends_on = None

def upgrade():
    # 索引1: 按模板ID查询（最常用）
    op.create_index(
        'idx_template_items_template_id_active',
        'template_items',
        ['template_id'],
        unique=False,
        postgresql_where=sa.text('is_deleted = false')
    )

    # 索引2: 按父节点ID查询（树形结构查询）
    op.create_index(
        'idx_template_items_parent_id_active',
        'template_items',
        ['parent_id'],
        unique=False,
        postgresql_where=sa.text('is_deleted = false AND parent_id IS NOT NULL')
    )

    # 索引3: 复合索引（模板ID + 父节点ID）用于优化树构建
    op.create_index(
        'idx_template_items_template_parent_active',
        'template_items',
        ['template_id', 'parent_id'],
        unique=False,
        postgresql_where=sa.text('is_deleted = false')
    )

    # 索引4: 优化软删除查询
    op.create_index(
        'idx_template_items_is_deleted',
        'template_items',
        ['is_deleted'],
        unique=False
    )

def downgrade():
    # 删除索引（按相反顺序）
    op.drop_index('idx_template_items_is_deleted', table_name='template_items')
    op.drop_index('idx_template_items_template_parent_active', table_name='template_items', postgresql_where=sa.text('is_deleted = false'))
    op.drop_index('idx_template_items_parent_id_active', table_name='template_items', postgresql_where=sa.text('is_deleted = false AND parent_id IS NOT NULL'))
    op.drop_index('idx_template_items_template_id_active', table_name='template_items', postgresql_where=sa.text('is_deleted = false'))
