from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class InspectionTaskBase(BaseModel):
    title: str = Field(..., max_length=300)
    template_id: Optional[UUID] = None
    assigned_to: Optional[UUID] = None
    target_name: Optional[str] = Field(None, max_length=200)
    target_address: Optional[str] = Field(None, max_length=500)
    target_contact: Optional[str] = Field(None, max_length=100)
    target_phone: Optional[str] = Field(None, max_length=20)
    scheduled_at: Optional[datetime] = None
    remarks: Optional[str] = None


class InspectionTaskCreate(InspectionTaskBase):
    pass


class InspectionTaskUpdate(BaseModel):
    title: Optional[str] = None
    template_id: Optional[UUID] = None
    assigned_to: Optional[UUID] = None
    target_name: Optional[str] = None
    target_address: Optional[str] = None
    target_contact: Optional[str] = None
    target_phone: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    remarks: Optional[str] = None
    status: Optional[str] = None


class InspectionTaskResponse(InspectionTaskBase):
    id: UUID
    task_no: str
    assigned_by: Optional[UUID] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str
    created_at: datetime
    updated_at: datetime
    audit_project_id: Optional[UUID] = None
    plan_item_id: Optional[UUID] = None
    area_name: Optional[str] = None
    clauses: Optional[List[str]] = None

    class Config:
        from_attributes = True


class InspectionRecordBase(BaseModel):
    template_item_id: Optional[UUID] = None
    result: Optional[str] = None
    result_value: Optional[str] = None
    result_text: Optional[str] = None
    inspector_note: Optional[str] = None


class InspectionRecordCreate(InspectionRecordBase):
    pass


class InspectionRecordUpdate(BaseModel):
    result: Optional[str] = None
    result_value: Optional[str] = None
    result_text: Optional[str] = None
    inspector_note: Optional[str] = None


class InspectionRecordResponse(InspectionRecordBase):
    id: UUID
    task_id: UUID
    llm_suggestion: Optional[str]
    llm_basis: Optional[str]
    recorded_by: Optional[UUID]
    recorded_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InspectionSummary(BaseModel):
    total: int
    completed: int
    compliant: int
    non_compliant: int
    not_applicable: int
    compliance_rate: float
