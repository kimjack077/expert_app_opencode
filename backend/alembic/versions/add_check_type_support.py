"""add check_type support

Revision ID: add_check_type_support
Revises: create_inspection_records
Create Date: 2026-03-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision = 'add_check_type_support'
down_revision = 'create_inspection_records'
branch_labels = None
depends_on = None


def upgrade():
    # 添加 template_items 表的新字段
    op.add_column('template_items', sa.Column('check_type', sa.String(20), nullable=True, comment='检查类型：score/radio/numeric/text/multi_check'))
    op.add_column('template_items', sa.Column('max_score', sa.Numeric, nullable=True, comment='打分类型最大分数'))
    op.add_column('template_items', sa.Column('score_step', sa.Numeric, nullable=True, comment='打分步长'))
    op.add_column('template_items', sa.Column('pass_score', sa.Numeric, nullable=True, comment='合格分数线'))

    # 添加 inspection_record_items 表的新字段
    op.add_column('inspection_record_items', sa.Column('score_value', sa.String(20), nullable=True, comment='打分类型结果'))
    op.add_column('inspection_record_items', sa.Column('radio_value', sa.String(100), nullable=True, comment='单选类型结果'))
    op.add_column('inspection_record_items', sa.Column('multi_value', JSON, nullable=True, comment='多选类型结果列表'))
    op.add_column('inspection_record_items', sa.Column('numeric_value', sa.String(50), nullable=True, comment='数值类型结果'))
    op.add_column('inspection_record_items', sa.Column('text_value', sa.Text, nullable=True, comment='文本类型结果'))
    op.add_column('inspection_record_items', sa.Column('problem_description', sa.Text, nullable=True, comment='问题描述'))
    op.add_column('inspection_record_items', sa.Column('rectification_suggestion', sa.Text, nullable=True, comment='整改建议'))
    op.add_column('inspection_record_items', sa.Column('ai_generated', sa.Boolean, nullable=True, default=False, comment='是否为AI生成'))
    op.add_column('inspection_record_items', sa.Column('ai_suggestion', sa.Text, nullable=True, comment='AI建议内容'))
    op.add_column('inspection_record_items', sa.Column('ai_basis', sa.Text, nullable=True, comment='AI法规依据'))

    # 更新现有数据：将 result_type='pass_fail' 的记录设置为 check_type='radio'
    op.execute("""
        UPDATE template_items
        SET check_type = CASE
            WHEN result_type = 'pass_fail' THEN 'radio'
            WHEN result_type = 'numeric' THEN 'numeric'
            WHEN result_type = 'text' THEN 'text'
            ELSE 'radio'
        END
        WHERE check_type IS NULL
    """)

    # 设置默认值
    op.execute("ALTER TABLE template_items ALTER COLUMN check_type SET DEFAULT 'radio'")


def downgrade():
    # 删除 inspection_record_items 表的新字段
    op.drop_column('inspection_record_items', 'ai_basis')
    op.drop_column('inspection_record_items', 'ai_suggestion')
    op.drop_column('inspection_record_items', 'ai_generated')
    op.drop_column('inspection_record_items', 'rectification_suggestion')
    op.drop_column('inspection_record_items', 'problem_description')
    op.drop_column('inspection_record_items', 'text_value')
    op.drop_column('inspection_record_items', 'numeric_value')
    op.drop_column('inspection_record_items', 'multi_value')
    op.drop_column('inspection_record_items', 'radio_value')
    op.drop_column('inspection_record_items', 'score_value')

    # 删除 template_items 表的新字段
    op.drop_column('template_items', 'pass_score')
    op.drop_column('template_items', 'score_step')
    op.drop_column('template_items', 'max_score')
    op.drop_column('template_items', 'check_type')