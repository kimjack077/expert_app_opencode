"""
Agent Conversation Models

Persisted chat history for the field-inspection AI agent, so a conversation
survives a page refresh or a device switch instead of living only in the
frontend's in-memory message array.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from ..database import Base


class AgentConversation(Base):
    """A single agent chat session, scoped to one user and (usually) one inspection record."""
    __tablename__ = "agent_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属用户 ID",
    )
    title = Column(String(200), comment="会话标题（默认取首条消息摘要）")
    context = Column(JSON, comment="上下文信息：record_id / current_item_id / enterprise_id 等")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", backref="agent_conversations")
    messages = relationship(
        "AgentMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AgentMessage.created_at",
    )

    def __repr__(self):
        return f"<AgentConversation {self.id}>"


class AgentMessage(Base):
    """A single message within an agent conversation."""
    __tablename__ = "agent_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_conversations.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属会话 ID",
    )
    role = Column(String(20), nullable=False, comment="'user' | 'assistant' | 'tool'")
    content = Column(Text, comment="消息文本内容")
    tool_calls = Column(JSON, comment="Function Calling 记录（工具名、参数、结果）")
    extra_data = Column(JSON, comment="额外元数据，如动作确认卡片的状态")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("AgentConversation", back_populates="messages")

    def __repr__(self):
        return f"<AgentMessage {self.id} role={self.role}>"
