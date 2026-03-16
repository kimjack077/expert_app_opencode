from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Integer, Numeric, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from ..database import Base


class Enterprise(Base):
    __tablename__ = "enterprises"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    credit_code = Column(String(50), unique=True, index=True)
    org_code = Column(String(50), index=True)
    industry_id = Column(UUID(as_uuid=True), ForeignKey("industries.id", ondelete="SET NULL"), nullable=True)
    address = Column(String(500))
    legal_person = Column(String(50))
    contact_person = Column(String(50))
    contact_phone = Column(String(20))
    enterprise_type = Column(String(50))
    economic_type = Column(String(50))
    risk_level = Column(String(20), default="B")
    status = Column(String(20), default="active")
    longitude = Column(Numeric(10, 7))
    latitude = Column(Numeric(10, 7))
    district = Column(String(50))
    street = Column(String(100))
    employee_count = Column(Integer)
    annual_output = Column(Numeric(15, 2))
    annual_tax = Column(Numeric(15, 2))
    remarks = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    qualifications = relationship("EnterpriseQualification", back_populates="enterprise", cascade="all, delete-orphan")
    products = relationship("EnterpriseProduct", back_populates="enterprise", cascade="all, delete-orphan")
    equipment = relationship("EnterpriseEquipment", back_populates="enterprise", cascade="all, delete-orphan")
    instruments = relationship("EnterpriseInstrument", back_populates="enterprise", cascade="all, delete-orphan")
    personnel = relationship("EnterprisePersonnel", back_populates="enterprise", cascade="all, delete-orphan")
    rectifications = relationship("RectificationRecord", back_populates="enterprise", cascade="all, delete-orphan")
    industry = relationship("Industry")


class EnterpriseQualification(Base):
    __tablename__ = "enterprise_qualifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enterprise_id = Column(UUID(as_uuid=True), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    qual_type = Column(String(50), nullable=False)
    cert_no = Column(String(100))
    product_name = Column(String(200))
    issue_date = Column(Date)
    valid_from = Column(Date)
    valid_until = Column(Date)
    issue_authority = Column(String(200))
    status = Column(String(20), default="valid")
    remarks = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    enterprise = relationship("Enterprise", back_populates="qualifications")


class EnterpriseProduct(Base):
    __tablename__ = "enterprise_products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enterprise_id = Column(UUID(as_uuid=True), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    category = Column(String(100))
    specification = Column(String(200))
    output_unit = Column(String(20))
    annual_output = Column(Numeric(15, 2))
    cert_status = Column(String(20))
    remarks = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    enterprise = relationship("Enterprise", back_populates="products")


class EnterpriseEquipment(Base):
    __tablename__ = "enterprise_equipment"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enterprise_id = Column(UUID(as_uuid=True), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    model = Column(String(100))
    manufacturer = Column(String(200))
    purchase_date = Column(Date)
    status = Column(String(20), default="normal")
    remarks = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    enterprise = relationship("Enterprise", back_populates="equipment")


class EnterpriseInstrument(Base):
    __tablename__ = "enterprise_instruments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enterprise_id = Column(UUID(as_uuid=True), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    model = Column(String(100))
    serial_no = Column(String(100))
    measure_range = Column(String(100))
    accuracy = Column(String(50))
    verification_method = Column(String(50))
    last_verified = Column(Date)
    next_verified = Column(Date)
    status = Column(String(20), default="normal")
    remarks = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    enterprise = relationship("Enterprise", back_populates="instruments")


class EnterprisePersonnel(Base):
    __tablename__ = "enterprise_personnel"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enterprise_id = Column(UUID(as_uuid=True), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(50), nullable=False)
    position = Column(String(50))
    phone = Column(String(20))
    id_card = Column(String(20))
    education = Column(String(50))
    certificate = Column(String(100))
    cert_valid_until = Column(Date)
    remarks = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    enterprise = relationship("Enterprise", back_populates="personnel")


class RectificationRecord(Base):
    __tablename__ = "rectification_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enterprise_id = Column(UUID(as_uuid=True), ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(UUID(as_uuid=True), ForeignKey("inspection_tasks.id"))
    issue_description = Column(Text, nullable=False)
    rectification_requirement = Column(Text)
    deadline = Column(Date)
    status = Column(String(20), default="pending")
    rectification_result = Column(Text)
    rectified_at = Column(DateTime(timezone=True))
    reviewer = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewed_at = Column(DateTime(timezone=True))
    transfer_to_inspection = Column(Boolean, default=False)
    transfer_no = Column(String(50))
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    enterprise = relationship("Enterprise", back_populates="rectifications")
    task = relationship("InspectionTask")
