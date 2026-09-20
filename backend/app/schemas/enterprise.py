from datetime import datetime, date
from typing import Literal, Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict
from uuid import UUID

# 风险等级（与前端 Enterprises 表单选项一致）：A级低风险 / B级一般 / C级较高 / D级高风险
RiskLevel = Literal["A", "B", "C", "D"]


class EnterpriseBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    credit_code: Optional[str] = Field(None, max_length=50)
    org_code: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    legal_person: Optional[str] = Field(None, max_length=50)
    contact_person: Optional[str] = Field(None, max_length=50)
    contact_phone: Optional[str] = Field(None, max_length=20)
    enterprise_type: Optional[str] = Field(None, max_length=50)
    economic_type: Optional[str] = Field(None, max_length=50)
    risk_level: Optional[RiskLevel] = "B"
    status: Optional[Literal["active", "suspended", "revoked"]] = "active"
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    district: Optional[str] = None
    street: Optional[str] = None
    employee_count: Optional[int] = Field(None, ge=0)
    annual_output: Optional[float] = Field(None, ge=0)
    annual_tax: Optional[float] = Field(None, ge=0)
    remarks: Optional[str] = None

    @field_validator(
        "credit_code", "org_code", "address", "legal_person",
        "contact_person", "contact_phone", "enterprise_type",
        "economic_type", "district", "street", "remarks",
        mode="before"
    )
    @classmethod
    def empty_str_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("longitude", "latitude", "employee_count", "annual_output", "annual_tax", mode="before")
    @classmethod
    def empty_number_to_none(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v


class EnterpriseCreate(EnterpriseBase):
    pass


class EnterpriseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    credit_code: Optional[str] = Field(None, max_length=50)
    org_code: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    legal_person: Optional[str] = Field(None, max_length=50)
    contact_person: Optional[str] = Field(None, max_length=50)
    contact_phone: Optional[str] = Field(None, max_length=20)
    enterprise_type: Optional[str] = Field(None, max_length=50)
    economic_type: Optional[str] = Field(None, max_length=50)
    risk_level: Optional[RiskLevel] = None
    status: Optional[Literal["active", "suspended", "revoked"]] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    district: Optional[str] = None
    street: Optional[str] = None
    employee_count: Optional[int] = Field(None, ge=0)
    annual_output: Optional[float] = Field(None, ge=0)
    annual_tax: Optional[float] = Field(None, ge=0)
    remarks: Optional[str] = None

    @field_validator(
        "name", "credit_code", "org_code", "address", "legal_person",
        "contact_person", "contact_phone", "enterprise_type",
        "economic_type", "district", "street", "remarks", "risk_level", "status",
        mode="before"
    )
    @classmethod
    def empty_str_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("longitude", "latitude", "employee_count", "annual_output", "annual_tax", mode="before")
    @classmethod
    def empty_number_to_none(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v


class EnterpriseResponse(EnterpriseBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    # 响应层放宽为 str：兼容历史脏数据（非法等级/状态值），避免序列化 500；
    # 严格枚举校验仅作用于 Create/Update 入参。
    risk_level: Optional[str] = None
    status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


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
    enterprise_id: Optional[UUID] = None


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

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    name: str
    category: Optional[str] = None
    specification: Optional[str] = None
    output_unit: Optional[str] = None
    annual_output: Optional[float] = None
    cert_status: Optional[str] = None
    remarks: Optional[str] = None


class ProductCreate(ProductBase):
    enterprise_id: Optional[UUID] = None


class RectificationReviewRequest(BaseModel):
    status: str
    rectification_result: Optional[str] = None


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

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


class EnterpriseDetail(EnterpriseResponse):
    qualifications: List[QualificationResponse] = []
    products: List[ProductResponse] = []
