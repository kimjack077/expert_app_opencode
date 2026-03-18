"""
审核项目相关 Pydantic Schemas
Audit Project Related Schemas
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ==================== AuditProject Schemas ====================

class AuditProjectBase(BaseModel):
    """审核项目基础 Schema"""
    title: str = Field(..., description="项目名称")
    enterprise_id: UUID = Field(..., description="受审核企业 ID")
    audit_type: str = Field(..., description="审核类型：initial/surveillance/recertification/expansion")
    certification_systems: List[str] = Field(default=[], description="认证体系列表：Q/E/S/En")
    audit_criteria: List[str] = Field(default=[], description="审核准则列表")
    audit_scope: Optional[dict] = Field(None, description="审核范围")
    scheduled_start: Optional[datetime] = Field(None, description="计划开始时间")
    scheduled_end: Optional[datetime] = Field(None, description="计划结束时间")
    audit_days: Optional[Decimal] = Field(None, description="审核人天数")
    team_leader_id: Optional[UUID] = Field(None, description="审核组长 ID")
    remarks: Optional[str] = Field(None, description="备注")


class AuditProjectCreate(AuditProjectBase):
    """创建审核项目"""
    pass


class AuditProjectUpdate(BaseModel):
    """更新审核项目"""
    title: Optional[str] = None
    audit_type: Optional[str] = None
    certification_systems: Optional[List[str]] = None
    audit_criteria: Optional[List[str]] = None
    audit_scope: Optional[dict] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    audit_days: Optional[Decimal] = None
    team_leader_id: Optional[UUID] = None
    status: Optional[str] = None
    remarks: Optional[str] = None


class AuditProjectResponse(AuditProjectBase):
    """审核项目响应"""
    id: UUID
    project_no: str
    status: str
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== AuditTeamMember Schemas ====================

class AuditTeamMemberBase(BaseModel):
    """审核组成员基础 Schema"""
    member_id: UUID = Field(..., description="审核员 ID")
    role: str = Field(default="member", description="角色：leader/member/trainee/observer/expert")
    responsible_systems: List[str] = Field(default=[], description="负责的认证体系")
    qualification_codes: List[str] = Field(default=[], description="专业代码列表")
    registration_no: Optional[str] = Field(None, description="注册审核员编号")
    registration_level: Optional[str] = Field(None, description="注册级别")
    assigned_areas: List[str] = Field(default=[], description="负责审核的区域/部门列表")
    assigned_clauses: List[str] = Field(default=[], description="负责审核的标准条款列表")


class AuditTeamMemberCreate(AuditTeamMemberBase):
    """创建审核组成员"""
    project_id: UUID = Field(..., description="所属审核项目 ID")


class AuditTeamMemberUpdate(BaseModel):
    """更新审核组成员"""
    role: Optional[str] = None
    responsible_systems: Optional[List[str]] = None
    qualification_codes: Optional[List[str]] = None
    assigned_areas: Optional[List[str]] = None
    assigned_clauses: Optional[List[str]] = None
    status: Optional[str] = None


class AuditTeamMemberResponse(AuditTeamMemberBase):
    """审核组成员响应"""
    id: UUID
    project_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== AuditPlanItem Schemas ====================

class AuditPlanItemBase(BaseModel):
    """审核计划项基础 Schema"""
    plan_date: date = Field(..., description="审核日期")
    time_start: Optional[str] = Field(None, description="开始时间")
    time_end: Optional[str] = Field(None, description="结束时间")
    group_no: Optional[str] = Field(None, description="工作组编号")
    area_name: str = Field(..., description="区域/部门名称")
    area_type: Optional[str] = Field(None, description="区域类型")
    assigned_member_ids: List[UUID] = Field(default=[], description="分配的审核员 ID 列表")
    certification_systems: List[str] = Field(default=[], description="本次任务审核的体系")
    clauses: List[str] = Field(default=[], description="具体条款列表")
    template_id: Optional[UUID] = Field(None, description="关联的检查模板 ID")
    is_joint: bool = Field(default=False, description="是否为联合审核")
    joint_group_ids: List[str] = Field(default=[], description="联合的其他组标识列表")
    activity_type: str = Field(default="normal", description="活动类型")
    remarks: Optional[str] = Field(None, description="备注")


class AuditPlanItemCreate(AuditPlanItemBase):
    """创建审核计划项"""
    project_id: UUID = Field(..., description="所属审核项目 ID")


class AuditPlanItemUpdate(BaseModel):
    """更新审核计划项"""
    plan_date: Optional[date] = None
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    group_no: Optional[str] = None
    area_name: Optional[str] = None
    area_type: Optional[str] = None
    assigned_member_ids: Optional[List[UUID]] = None
    certification_systems: Optional[List[str]] = None
    clauses: Optional[List[str]] = None
    template_id: Optional[UUID] = None
    is_joint: Optional[bool] = None
    joint_group_ids: Optional[List[str]] = None
    activity_type: Optional[str] = None
    status: Optional[str] = None
    remarks: Optional[str] = None


class AuditPlanItemResponse(AuditPlanItemBase):
    """审核计划项响应"""
    id: UUID
    project_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== AuditArea Schemas ====================

class AuditAreaBase(BaseModel):
    """审核区域基础 Schema"""
    area_name: str = Field(..., description="区域名称")
    area_type: Optional[str] = Field(None, description="区域类型")
    responsible_team_member_ids: List[UUID] = Field(default=[], description="负责的审核员 ID 列表")
    audit_clauses: List[str] = Field(default=[], description="审核条款列表")


class AuditAreaCreate(AuditAreaBase):
    """创建审核区域"""
    project_id: UUID = Field(..., description="所属审核项目 ID")


class AuditAreaUpdate(BaseModel):
    """更新审核区域"""
    area_name: Optional[str] = None
    area_type: Optional[str] = None
    responsible_team_member_ids: Optional[List[UUID]] = None
    audit_clauses: Optional[List[str]] = None
    status: Optional[str] = None


class AuditAreaResponse(AuditAreaBase):
    """审核区域响应"""
    id: UUID
    project_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== AuditAreaRecord Schemas ====================

class AuditAreaRecordBase(BaseModel):
    """审核区域记录基础 Schema"""
    area_id: Optional[UUID] = Field(None, description="审核区域 ID")
    plan_item_id: Optional[UUID] = Field(None, description="关联的审核计划项 ID")
    template_id: Optional[UUID] = Field(None, description="使用的模板 ID")
    certification_systems: List[str] = Field(default=[], description="本记录涉及的体系")
    co_recorders: List[UUID] = Field(default=[], description="协作填写人 ID 列表")
    audit_date: Optional[date] = Field(None, description="审核日期")
    audit_time_start: Optional[str] = Field(None, description="审核开始时间")
    audit_time_end: Optional[str] = Field(None, description="审核结束时间")
    conclusion: Optional[str] = Field(None, description="审核结论")


class AuditAreaRecordRequest(AuditAreaRecordBase):
    """创建审核区域记录请求（project_id 从路径获取，recorded_by 从当前用户获取）"""
    pass


class AuditAreaRecordCreate(AuditAreaRecordBase):
    """创建审核区域记录（完整字段，用于内部调用）"""
    project_id: UUID = Field(..., description="所属审核项目 ID")
    recorded_by: UUID = Field(..., description="主填写人 ID")


class AuditAreaRecordUpdate(BaseModel):
    """更新审核区域记录"""
    area_id: Optional[UUID] = None
    template_id: Optional[UUID] = None
    certification_systems: Optional[List[str]] = None
    co_recorders: Optional[List[UUID]] = None
    audit_date: Optional[date] = None
    audit_time_start: Optional[str] = None
    audit_time_end: Optional[str] = None
    conclusion: Optional[str] = None
    status: Optional[str] = None


class AuditAreaRecordResponse(AuditAreaRecordBase):
    """审核区域记录响应"""
    id: UUID
    project_id: UUID
    record_no: Optional[str] = None
    recorded_by: UUID
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== Nonconformity Schemas ====================

class NonconformityBase(BaseModel):
    """不符合项基础 Schema"""
    severity: str = Field(..., description="严重程度：major/minor/observation")
    certification_system: Optional[str] = Field(None, description="涉及的认证体系")
    clause_no: Optional[str] = Field(None, description="涉及的标准条款号")
    description: str = Field(..., description="不符合描述")
    evidence: Optional[str] = Field(None, description="客观证据")
    corrective_action_required: Optional[str] = Field(None, description="整改要求")
    due_date: Optional[date] = Field(None, description="整改期限")


class NonconformityRequest(NonconformityBase):
    """创建不符合项请求（project_id 从路径获取）"""
    plan_item_id: Optional[UUID] = Field(None, description="来源于哪个审核计划项")
    area_record_id: Optional[UUID] = Field(None, description="来源于哪个区域记录")
    record_item_id: Optional[UUID] = Field(None, description="来源于哪个检查记录项")


class NonconformityCreate(NonconformityBase):
    """创建不符合项（完整字段，用于内部调用）"""
    project_id: UUID = Field(..., description="所属审核项目 ID")
    plan_item_id: Optional[UUID] = Field(None, description="来源于哪个审核计划项")
    area_record_id: Optional[UUID] = Field(None, description="来源于哪个区域记录")
    record_item_id: Optional[UUID] = Field(None, description="来源于哪个检查记录项")


class NonconformityUpdate(BaseModel):
    """更新不符合项"""
    severity: Optional[str] = None
    certification_system: Optional[str] = None
    clause_no: Optional[str] = None
    description: Optional[str] = None
    evidence: Optional[str] = None
    corrective_action_required: Optional[str] = None
    due_date: Optional[date] = None
    corrective_action: Optional[str] = None
    correction_date: Optional[date] = None
    verification_result: Optional[str] = None
    verification_photos: Optional[List[str]] = None
    status: Optional[str] = None
    verified_by: Optional[UUID] = None


class NonconformityResponse(NonconformityBase):
    """不符合项响应"""
    id: UUID
    project_id: UUID
    nc_no: str
    plan_item_id: Optional[UUID] = None
    area_record_id: Optional[UUID] = None
    record_item_id: Optional[UUID] = None
    corrective_action: Optional[str] = None
    correction_date: Optional[date] = None
    verification_result: Optional[str] = None
    verification_photos: List[str] = []
    status: str
    created_by: Optional[UUID] = None
    verified_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== AuditReport Schemas ====================

class AuditReportBase(BaseModel):
    """审核报告基础 Schema"""
    report_type: str = Field(..., description="报告类型：QES/EnMS/combined")
    audit_summary: Optional[dict] = Field(None, description="审核过程综述")
    system_evaluation: Optional[dict] = Field(None, description="管理体系综合评价")
    narrative_text: Optional[str] = Field(None, description="叙述性综合评价")
    findings_summary: Optional[dict] = Field(None, description="审核发现统计")
    nonconformity_ids: List[UUID] = Field(default=[], description="不符合项 ID 列表")
    improvement_opportunities: Optional[str] = Field(None, description="改进机会列表")
    conclusion: Optional[str] = Field(None, description="审核结论")
    conclusion_notes: Optional[str] = Field(None, description="结论说明")


class AuditReportCreate(AuditReportBase):
    """创建审核报告"""
    project_id: UUID = Field(..., description="所属审核项目 ID")


class AuditReportUpdate(BaseModel):
    """更新审核报告"""
    report_type: Optional[str] = None
    audit_summary: Optional[dict] = None
    system_evaluation: Optional[dict] = None
    narrative_text: Optional[str] = None
    findings_summary: Optional[dict] = None
    nonconformity_ids: Optional[List[UUID]] = None
    improvement_opportunities: Optional[str] = None
    conclusion: Optional[str] = None
    conclusion_notes: Optional[str] = None
    prepared_by: Optional[UUID] = None
    reviewed_by: Optional[UUID] = None
    approved_by: Optional[UUID] = None


class AuditReportResponse(AuditReportBase):
    """审核报告响应"""
    id: UUID
    project_id: UUID
    report_no: Optional[str] = None
    prepared_by: Optional[UUID] = None
    reviewed_by: Optional[UUID] = None
    approved_by: Optional[UUID] = None
    prepared_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== CommunicationMeeting Schemas ====================

class CommunicationMeetingBase(BaseModel):
    """沟通会议基础 Schema"""
    meeting_type: str = Field(..., description="会议类型：opening/interim/closing/internal")
    meeting_time: datetime = Field(..., description="会议时间")
    participants_enterprise: Optional[str] = Field(None, description="企业参会人员")
    participants_audit_team: List[UUID] = Field(default=[], description="审核组参会人员 ID 列表")
    key_points: Optional[str] = Field(None, description="会议要点")
    meeting_minutes: Optional[str] = Field(None, description="会议纪要")
    sign_in_sheet: Optional[dict] = Field(None, description="签到表")


class CommunicationMeetingCreate(CommunicationMeetingBase):
    """创建沟通会议"""
    project_id: UUID = Field(..., description="所属审核项目 ID")


class CommunicationMeetingUpdate(BaseModel):
    """更新沟通会议"""
    meeting_type: Optional[str] = None
    meeting_time: Optional[datetime] = None
    participants_enterprise: Optional[str] = None
    participants_audit_team: Optional[List[UUID]] = None
    key_points: Optional[str] = None
    meeting_minutes: Optional[str] = None
    sign_in_sheet: Optional[dict] = None


class CommunicationMeetingResponse(CommunicationMeetingBase):
    """沟通会议响应"""
    id: UUID
    project_id: UUID
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
