from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, Optional, List
from datetime import datetime
from uuid import UUID

# 检查结论枚举：三选一 + 历史兼容别名（not_applicable），其余值一律拒绝
CheckResult = Literal["pass", "fail", "na", "not_applicable"]


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

    model_config = ConfigDict(from_attributes=True)


class InspectionRecordBase(BaseModel):
    template_item_id: Optional[UUID] = None
    result: Optional[CheckResult] = None
    result_value: Optional[str] = None
    result_text: Optional[str] = None
    inspector_note: Optional[str] = None

    # 任务填报是数据写入入口。未知字段若被静默忽略，会让调用方收到“成功”但
    # 实际没有保存（例如误传 radio_value）；应直接返回 422 暴露契约错误。
    model_config = ConfigDict(extra="forbid")


class InspectionRecordCreate(InspectionRecordBase):
    template_item_id: UUID = Field(..., description="绑定的模板检查项ID")
    media_ids: Optional[List[UUID]] = None


class InspectionRecordUpdate(BaseModel):
    result: Optional[CheckResult] = None
    result_value: Optional[str] = None
    result_text: Optional[str] = None
    inspector_note: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class InspectionRecordResponse(InspectionRecordBase):
    id: UUID
    task_id: UUID
    llm_suggestion: Optional[str]
    llm_basis: Optional[str]
    recorded_by: Optional[UUID]
    recorded_at: datetime
    updated_at: datetime
    # 响应层放宽为 str：兼容历史脏数据，避免序列化 500
    result: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InspectionSummary(BaseModel):
    total: int
    completed: int
    compliant: int
    non_compliant: int
    not_applicable: int
    compliance_rate: float
