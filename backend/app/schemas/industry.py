from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class IndustryBase(BaseModel):
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[UUID] = None
    sort_order: int = 0
    icon: Optional[str] = None
    is_active: bool = True

class IndustryCreate(IndustryBase):
    pass

class IndustryUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[UUID] = None
    sort_order: Optional[int] = None
    icon: Optional[str] = None
    is_active: Optional[bool] = None

class IndustryResponse(IndustryBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class IndustryTreeResponse(BaseModel):
    id: UUID
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[UUID] = None
    sort_order: int = 0
    icon: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    children: List['IndustryTreeResponse'] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

IndustryTreeResponse.model_rebuild()
