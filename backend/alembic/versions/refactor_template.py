"""refactor template structure

Revision ID: refactor_template
Revises: add_enterprise_knowledge
Create Date: 2026-03-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'refactor_template'
down_revision = 'add_enterprise_knowledge'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 使用原生 SQL 删除表（带 CASCADE）
    op.execute('DROP TABLE IF EXISTS template_items CASCADE')
    op.execute('DROP TABLE IF EXISTS check_items CASCADE')
    op.execute('DROP TABLE IF EXISTS standard_categories CASCADE')
    
    # 创建新的 template_items 表
    op.create_table(
        'template_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('check_method', sa.Text(), nullable=True),
        sa.Column('legal_basis', sa.Text(), nullable=True),
        sa.Column('standard_ref', sa.String(length=200), nullable=True),
        sa.Column('result_type', sa.String(length=20), nullable=True),
        sa.Column('result_options', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('min_value', sa.Numeric(), nullable=True),
        sa.Column('max_value', sa.Numeric(), nullable=True),
        sa.Column('unit', sa.String(length=50), nullable=True),
        sa.Column('is_required', sa.Boolean(), nullable=True),
        sa.Column('risk_level', sa.String(length=20), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('tags', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('is_category', sa.Boolean(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['template_id'], ['inspection_templates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_id'], ['template_items.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 创建 task_item_records 表
    op.create_table(
        'task_item_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('template_item_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('result', sa.String(length=20), nullable=True),
        sa.Column('result_value', sa.String(length=50), nullable=True),
        sa.Column('result_text', sa.Text(), nullable=True),
        sa.Column('inspector_note', sa.Text(), nullable=True),
        sa.Column('llm_suggestion', sa.Text(), nullable=True),
        sa.Column('llm_basis', sa.Text(), nullable=True),
        sa.Column('recorded_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['inspection_tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['template_item_id'], ['template_items.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 更新 inspection_templates 表的注释
    op.alter_column('inspection_templates', 'name',
               existing_type=sa.VARCHAR(length=200),
               comment='模板名称，如：食品安全检查模板',
               existing_nullable=False)
    op.alter_column('inspection_templates', 'code',
               existing_type=sa.VARCHAR(length=50),
               comment='模板编码',
               existing_nullable=True)
    op.alter_column('inspection_templates', 'description',
               existing_type=sa.TEXT(),
               comment='模板描述',
               existing_nullable=True)
    op.alter_column('inspection_templates', 'category',
               existing_type=sa.VARCHAR(length=100),
               comment='模板类别，如：食品安全、安全生产',
               existing_nullable=True)
    op.alter_column('inspection_templates', 'version',
               existing_type=sa.VARCHAR(length=20),
               comment='版本号',
               existing_nullable=True)
    op.alter_column('inspection_templates', 'is_published',
               existing_type=sa.BOOLEAN(),
               comment='是否已发布',
               existing_nullable=True)


def downgrade() -> None:
    # 恢复旧的表结构
    op.drop_table('task_item_records')
    op.drop_table('template_items')
    
    # 重新创建旧表
    op.create_table(
        'standard_categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=True),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('legal_basis', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table(
        'check_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('check_method', sa.Text(), nullable=True),
        sa.Column('legal_basis', sa.Text(), nullable=True),
        sa.Column('standard_ref', sa.String(length=200), nullable=True),
        sa.Column('result_type', sa.String(length=20), nullable=True),
        sa.Column('result_options', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('is_required', sa.Boolean(), nullable=True),
        sa.Column('risk_level', sa.String(length=20), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('tags', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['category_id'], ['standard_categories.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table(
        'template_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('check_item_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('is_required', sa.Boolean(), nullable=True),
        sa.Column('custom_title', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['template_id'], ['inspection_templates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['check_item_id'], ['check_items.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
