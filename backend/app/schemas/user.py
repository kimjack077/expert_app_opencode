from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Literal, Optional, List
from datetime import datetime
from uuid import UUID

# 系统内置角色（与 app/utils/roles.py 保持一致），禁止写入其他值
UserRole = Literal["super_admin", "admin", "expert", "auditor"]


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    exp: datetime
    type: str


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)
    role: UserRole = "expert"
    org_id: Optional[UUID] = None
    industry_id: Optional[UUID] = None
    is_active: bool = True
    auditor_registration_no: Optional[str] = Field(None, description="注册审核员编号")
    auditor_level: Optional[str] = Field(None, description="注册级别：basic/intermediate/senior")
    qualified_systems: List[str] = Field(default=[], description="注册体系列表")
    qualified_industry_codes: List[str] = Field(default=[], description="专业代码列表")


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None
    org_id: Optional[UUID] = None
    industry_id: Optional[UUID] = None
    auditor_registration_no: Optional[str] = None
    auditor_level: Optional[str] = None
    qualified_systems: Optional[List[str]] = None
    qualified_industry_codes: Optional[List[str]] = None


class UserResponse(UserBase):
    id: UUID
    role: str
    is_active: bool
    org_id: Optional[UUID] = None
    industry_id: Optional[UUID] = None
    auditor_registration_no: Optional[str] = None
    auditor_level: Optional[str] = None
    qualified_systems: List[str] = []
    qualified_industry_codes: List[str] = []
    last_login_at: Optional[datetime] = None
    created_at: datetime

    @field_validator('qualified_systems', 'qualified_industry_codes', mode='before')
    @classmethod
    def ensure_list(cls, v):
        if v is None:
            return []
        return v

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)
