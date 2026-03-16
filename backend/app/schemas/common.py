from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class MediaFileBase(BaseModel):
    file_type: str = "image"
    original_name: Optional[str] = None
    lat: Optional[str] = None
    lng: Optional[str] = None


class MediaFileResponse(MediaFileBase):
    id: UUID
    task_id: Optional[UUID]
    record_id: Optional[UUID]
    stored_name: str
    file_path: str
    file_size: Optional[int]
    mime_type: Optional[str]
    thumbnail_path: Optional[str]
    uploaded_at: datetime

    class Config:
        from_attributes = True


class LLMRequest(BaseModel):
    task_id: UUID
    record_id: Optional[UUID] = None
    check_item_id: Optional[UUID] = None
    use_cache: bool = True


class LLMResponse(BaseModel):
    content: str
    cached: bool = False
    duration_ms: Optional[int] = None


class ApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: Optional[dict | list] = None
    timestamp: datetime

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
