from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


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
    role: str = "expert"
    org_id: Optional[UUID] = None
    industry_id: Optional[UUID] = None
    is_active: bool = True


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None
    org_id: Optional[UUID] = None
    industry_id: Optional[UUID] = None


class UserResponse(UserBase):
    id: UUID
    role: str
    is_active: bool
    org_id: Optional[UUID] = None
    industry_id: Optional[UUID] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)
