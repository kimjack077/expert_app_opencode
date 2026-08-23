"""add_markdown_path_to_knowledge_documents

Revision ID: 2ef58ca8bdd1
Revises: add_agent_runtime_v2
Create Date: 2026-08-23 18:55:50.509782

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2ef58ca8bdd1'
down_revision = 'add_agent_runtime_v2'
branch_labels = None
depends_on = None


def upgrade():
    # 仅添加 markdown_path 列，其余 autogenerate 检测到的差异均为历史兼容项，跳过
    op.add_column('knowledge_documents', sa.Column('markdown_path', sa.String(length=500), nullable=True))


def downgrade():
    op.drop_column('knowledge_documents', 'markdown_path')
