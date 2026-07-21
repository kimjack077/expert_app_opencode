from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from ..database import Base
from .base import SoftDeleteMixin


class KnowledgeDocument(Base, SoftDeleteMixin):
    __tablename__ = "knowledge_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # category_id 列仍保留在数据库中（历史兼容），业务层已弃用，不再映射
    title = Column(String(300), nullable=False)
    doc_type = Column(String(50))
    doc_no = Column(String(100))
    content = Column(Text)
    summary = Column(Text)
    keywords = Column(String(500))
    issue_authority = Column(String(200))
    issue_date = Column(DateTime(timezone=True))
    effective_date = Column(DateTime(timezone=True))
    expiry_date = Column(DateTime(timezone=True))
    status = Column(String(20), default="effective")
    file_url = Column(String(500))
    file_name = Column(String(200))
    # view_count 列仍保留在数据库中（历史兼容），业务层已弃用，不再映射/累加
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class InspectionGuideline(Base):
    __tablename__ = "inspection_guidelines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    code = Column(String(50))
    product_category = Column(String(100))
    content = Column(Text)
    legal_basis = Column(Text)
    version = Column(String(20), default="1.0")
    is_active = Column(Boolean, default=True)
    effective_date = Column(DateTime(timezone=True))
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
