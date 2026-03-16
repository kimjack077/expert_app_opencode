from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from ..database import Base


class KnowledgeCategory(Base):
    __tablename__ = "knowledge_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    code = Column(String(50))
    parent_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_categories.id"))
    category_type = Column(String(50))
    sort_order = Column(Integer, default=0)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    parent = relationship("KnowledgeCategory", remote_side=[id], backref="children")
    documents = relationship("KnowledgeDocument", back_populates="category")


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_categories.id"))
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
    view_count = Column(Integer, default=0)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    category = relationship("KnowledgeCategory", back_populates="documents")


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
