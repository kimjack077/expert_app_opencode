from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Text,
    Integer,
    BigInteger,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from ..database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    username = Column(String(50))
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50))
    resource_id = Column(String(100))
    detail = Column(JSON)
    ip_address = Column(String(50))
    user_agent = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LLMCallLog(Base):
    __tablename__ = "llm_call_logs"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    task_id = Column(UUID(as_uuid=True), nullable=True)
    record_id = Column(UUID(as_uuid=True), ForeignKey("inspection_records.id"))
    call_type = Column(String(20), nullable=False)
    prompt = Column(Text, nullable=False)
    response = Column(Text)
    model = Column(String(100))
    tokens_used = Column(Integer)
    duration_ms = Column(Integer)
    is_success = Column(String(10), default="true")
    error_msg = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
