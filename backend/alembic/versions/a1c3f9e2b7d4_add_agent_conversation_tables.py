"""add agent conversation and message tables

Revision ID: a1c3f9e2b7d4
Revises: db5085d66adb
Create Date: 2026-07-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1c3f9e2b7d4'
down_revision = 'db5085d66adb'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'agent_conversations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False, comment='所属用户 ID'),
        sa.Column('title', sa.String(length=200), nullable=True, comment='会话标题（默认取首条消息摘要）'),
        sa.Column('context', sa.JSON(), nullable=True, comment='上下文信息：record_id / current_item_id / enterprise_id 等'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_agent_conversations_user_id'), 'agent_conversations', ['user_id'], unique=False
    )

    op.create_table(
        'agent_messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False, comment='所属会话 ID'),
        sa.Column('role', sa.String(length=20), nullable=False, comment="'user' | 'assistant' | 'tool'"),
        sa.Column('content', sa.Text(), nullable=True, comment='消息文本内容'),
        sa.Column('tool_calls', sa.JSON(), nullable=True, comment='Function Calling 记录（工具名、参数、结果）'),
        sa.Column('extra_data', sa.JSON(), nullable=True, comment='额外元数据，如动作确认卡片的状态'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['agent_conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_agent_messages_conversation_id'), 'agent_messages', ['conversation_id'], unique=False
    )


def downgrade():
    op.drop_index(op.f('ix_agent_messages_conversation_id'), table_name='agent_messages')
    op.drop_table('agent_messages')
    op.drop_index(op.f('ix_agent_conversations_user_id'), table_name='agent_conversations')
    op.drop_table('agent_conversations')
