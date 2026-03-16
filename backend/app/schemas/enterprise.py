from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel
from uuid import UUID


class EnterpriseBase(BaseModel):
    name: str
    credit_code: Optional[str] = None
    org_code: Optional[str] = None
    address: Optional[str] = None
    legal_person: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    enterprise_type: Optional[str] = None
    economic_type: Optional[str] = None
    risk_level: Optional[str] = "B"
    status: Optional[str] = "active"
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    district: Optional[str] = None
    street: Optional[str] = None
    employee_count: Optional[int] = None
    annual_output: Optional[float] = None
    annual_tax: Optional[float] = None
    remarks: Optional[str] = None


class EnterpriseCreate(EnterpriseBase):
    pass


class EnterpriseUpdate(BaseModel):
    name: Optional[str] = None
    credit_code: Optional[str] = None
    org_code: Optional[str] = None
    address: Optional[str] = None
    legal_person: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    enterprise_type: Optional[str] = None
    economic_type: Optional[str] = None
    risk_level: Optional[str] = None
    status: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    district: Optional[str] = None
    street: Optional[str] = None
    employee_count: Optional[int] = None
    annual_output: Optional[float] = None
    annual_tax: Optional[float] = None
    remarks: Optional[str] = None


class EnterpriseResponse(EnterpriseBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class QualificationBase(BaseModel):
    qual_type: str
    cert_no: Optional[str] = None
    product_name: Optional[str] = None
    issue_date: Optional[date] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    issue_authority: Optional[str] = None
    status: Optional[str] = "valid"
    remarks: Optional[str] = None


class QualificationCreate(QualificationBase):
    enterprise_id: UUID


class QualificationUpdate(BaseModel):
    qual_type: Optional[str] = None
    cert_no: Optional[str] = None
    product_name: Optional[str] = None
    issue_date: Optional[date] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    issue_authority: Optional[str] = None
    status: Optional[str] = None
    remarks: Optional[str] = None


class QualificationResponse(QualificationBase):
    id: UUID
    enterprise_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductBase(BaseModel):
    name: str
    category: Optional[str] = None
    specification: Optional[str] = None
    output_unit: Optional[str] = None
    annual_output: Optional[float] = None
    cert_status: Optional[str] = None
    remarks: Optional[str] = None


class ProductCreate(ProductBase):
    enterprise_id: UUID


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    specification: Optional[str] = None
    output_unit: Optional[str] = None
    annual_output: Optional[float] = None
    cert_status: Optional[str] = None
    remarks: Optional[str] = None


class ProductResponse(ProductBase):
    id: UUID
    enterprise_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InstrumentBase(BaseModel):
    name: str
    model: Optional[str] = None
    serial_no: Optional[str] = None
    measure_range: Optional[str] = None
    accuracy: Optional[str] = None
    verification_method: Optional[str] = None
    last_verified: Optional[date] = None
    next_verified: Optional[date] = None
    status: Optional[str] = "normal"
    remarks: Optional[str] = None


class InstrumentCreate(InstrumentBase):
    enterprise_id: UUID


class InstrumentUpdate(BaseModel):
    name: Optional[str] = None
    model: Optional[str] = None
    serial_no: Optional[str] = None
    measure_range: Optional[str] = None
    accuracy: Optional[str] = None
    verification_method: Optional[str] = None
    last_verified: Optional[date] = None
    next_verified: Optional[date] = None
    status: Optional[str] = None
    remarks: Optional[str] = None


class InstrumentResponse(InstrumentBase):
    id: UUID
    enterprise_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RectificationBase(BaseModel):
    enterprise_id: UUID
    task_id: Optional[UUID] = None
    issue_description: str
    rectification_requirement: Optional[str] = None
    deadline: Optional[date] = None
    status: Optional[str] = "pending"
    rectification_result: Optional[str] = None
    rectified_at: Optional[datetime] = None
    transfer_to_inspection: Optional[bool] = False
    transfer_no: Optional[str] = None


class RectificationCreate(RectificationBase):
    pass


class RectificationUpdate(BaseModel):
    issue_description: Optional[str] = None
    rectification_requirement: Optional[str] = None
    deadline: Optional[date] = None
    status: Optional[str] = None
    rectification_result: Optional[str] = None
    rectified_at: Optional[datetime] = None
    reviewer: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    transfer_to_inspection: Optional[bool] = None
    transfer_no: Optional[str] = None


class RectificationResponse(RectificationBase):
    id: UUID
    reviewer: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EnterpriseDetail(EnterpriseResponse):
    qualifications: List[QualificationResponse] = []
    products: List[ProductResponse] = []
    instruments: List[InstrumentResponse] = []
