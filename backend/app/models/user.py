from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from ..database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    code = Column(String(50), unique=True)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    users = relationship("User", back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, index=True)
    phone = Column(String(20))
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    role = Column(String(20), nullable=False, default="expert")
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    industry_id = Column(UUID(as_uuid=True), ForeignKey("industries.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime(timezone=True))
    
    # 审核员资质信息（新增）
    auditor_registration_no = Column(String(100), comment="注册审核员编号，如 2022-N1QMS-2215455")
    auditor_level = Column(
        String(50),
        comment="注册级别：basic(初级审核员)/intermediate(中级审核员)/senior(高级审核员)"
    )
    qualified_systems = Column(
        JSON,
        default=list,
        comment="注册体系列表：['Q', 'E', 'S', 'En']"
    )
    qualified_industry_codes = Column(
        JSON,
        default=list,
        comment="专业代码列表：['10.01', '12.01'] 等，决定可审核哪些行业"
    )
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    organization = relationship("Organization", back_populates="users")
    industry = relationship("Industry")
