from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
import uuid

from ..database import Base

class Industry(Base):
    __tablename__ = "industries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True)
    description = Column(Text)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("industries.id", ondelete="SET NULL"))
    sort_order = Column(Integer, default=0)
    icon = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    children = relationship(
        "Industry",
        backref=backref("parent", remote_side=[id]),
        order_by="Industry.sort_order",
        cascade="all, delete-orphan"
    )
