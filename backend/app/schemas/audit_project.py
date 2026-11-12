"""
审核项目相关 Pydantic Schemas
Audit Project Related Schemas
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

# 审核类型：初审 / 监督审核 / 再认证 / 扩大范围
AuditType = Literal["initial", "surveillance", "recertification", "expansion"]
# 认证体系代码（与前端 AuditProjects/Create.tsx 选项一致）
CertificationSystem = Literal["Q", "E", "S", "En"]


def _validate_dates(start: Optional[datetime], end: Optional[datetime]) -> None:
    if start and end and end < start:
        raise ValueError("计划结束时间不能早于计划开始时间")


# ==================== AuditProject Schemas ====================

class AuditProjectBase(BaseModel):
    """审核项目基础 Schema"""
    title: str = Field(..., min_length=1, max_length=300, description="项目名称")
    enterprise_id: UUID = Field(..., description="受审核企业 ID")
    audit_type: AuditType = Field(..., description="审核类型：initial/surveillance/recertification/expansion")
    certification_systems: List[CertificationSystem] = Field(default=[], description="认证体系列表：Q/E/S/En")
    audit_criteria: List[str] = Field(default=[], description="审核准则列表")
    audit_scope: Optional[dict] = Field(None, description="审核范围")
    scheduled_start: Optional[datetime] = Field(None, description="计划开始时间")
    scheduled_end: Optional[datetime] = Field(None, description="计划结束时间")
    # 审核工作量（人天）：全体审核员现场工作天数之和，必须为正数且有合理上限
    audit_days: Optional[Decimal] = Field(None, gt=0, le=365, description="审核工作量（人天）")
    team_leader_id: Optional[UUID] = Field(None, description="审核组长 ID")
    remarks: Optional[str] = Field(None, description="备注")


class AuditProjectCreate(AuditProjectBase):
    """创建审核项目"""

    @model_validator(mode="after")
    def _check_schedule(self):
        # 排期交叉校验只作用于入参；Response 继承时不执行，避免历史脏数据导致序列化 500
        _validate_dates(self.scheduled_start, self.scheduled_end)
        return self


class AuditProjectUpdate(BaseModel):
    """更新审核项目"""
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    audit_type: Optional[AuditType] = None
    certification_systems: Optional[List[CertificationSystem]] = None
    audit_criteria: Optional[List[str]] = None
    audit_scope: Optional[dict] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    audit_days: Optional[Decimal] = Field(None, gt=0, le=365)
    team_leader_id: Optional[UUID] = None
    status: Optional[str] = None
    remarks: Optional[str] = None

    @model_validator(mode="after")
    def _check_schedule(self):
        _validate_dates(self.scheduled_start, self.scheduled_end)
        return self


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
    # 响应层放宽：兼容历史脏数据，避免序列化 500；严格校验仅作用于 Create/Update 入参。
    audit_type: Optional[str] = None
    certification_systems: Optional[List[str]] = None
    audit_days: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)


# ==================== AuditTeamMember Schemas ====================

# 审核组角色枚举（与前端及业务约定一致），其余值一律拒绝
TeamMemberRole = Literal["leader", "member", "trainee", "observer", "expert"]


class AuditTeamMemberBase(BaseModel):
    """审核组成员基础 Schema"""
    member_id: UUID = Field(..., description="审核员 ID")
    role: TeamMemberRole = Field(default="member", description="角色：leader/member/trainee/observer/expert")
    responsible_systems: List[str] = Field(default=[], description="负责的认证体系")
    qualification_codes: List[str] = Field(default=[], description="专业代码列表")
    registration_no: Optional[str] = Field(None, description="注册审核员编号")
    registration_level: Optional[str] = Field(None, description="注册级别")
    assigned_areas: List[str] = Field(default=[], description="负责审核的区域/部门列表")
    assigned_clauses: List[str] = Field(default=[], description="负责审核的标准条款列表")


class AuditTeamMemberCreate(AuditTeamMemberBase):
    """创建审核组成员

    project_id 可由路径参数提供，请求体可不传；若传了则以路径为准。
    """
    project_id: Optional[UUID] = Field(
        None, description="所属审核项目 ID（可选，优先使用路径参数）"
    )


class AuditTeamMemberUpdate(BaseModel):
    """更新审核组成员"""
    role: Optional[TeamMemberRole] = None
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
    member_name: Optional[str] = Field(None, description="审核员姓名")
    member_username: Optional[str] = Field(None, description="审核员用户名")
    created_at: datetime
    updated_at: datetime
    # 响应层放宽为 str：兼容历史脏数据（如非法角色值），避免序列化 500
    role: str = "member"

    model_config = ConfigDict(from_attributes=True)


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
    template_id: Optional[UUID] = Field(
        None,
        description="关联的检查模板 ID（检查类活动必填；首次/末次会议、内部沟通等会议类活动豁免）",
    )
    is_joint: bool = Field(default=False, description="是否为联合审核")
    joint_group_ids: List[str] = Field(default=[], description="联合的其他组标识列表")
    activity_type: str = Field(default="normal", description="活动类型")
    remarks: Optional[str] = Field(None, description="备注")


class AuditPlanItemCreate(AuditPlanItemBase):
    """创建审核计划项

    project_id 可由路径参数提供，请求体可不传；若传了则以路径为准。
    """
    project_id: Optional[UUID] = Field(
        None, description="所属审核项目 ID（可选，优先使用路径参数）"
    )

    @model_validator(mode="after")
    def _require_template_for_inspection(self):
        """检查类活动必须选择检查模板。

        没有模板的现场检查在执行时会加载出空白检查项，属于不可恢复的脏数据，
        因此在入口处直接拒绝（会议类活动不开展现场检查，豁免）。
        """
        from app.utils.activity import requires_template

        if requires_template(self.activity_type) and not self.template_id:
            raise ValueError("请选择检查模板（检查类审核活动必须绑定检查模板）")
        return self


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
    status: Optional[Literal["pending", "in_progress", "completed", "cancelled"]] = None
    remarks: Optional[str] = None

    @model_validator(mode="after")
    def _require_template_for_inspection(self):
        """显式清空模板、且活动类型一并给出时，检查类活动一律拒绝。

        这里只看请求体**同时**给出的这两个字段；单独修改活动类型（未动模板）的
        部分更新由路由层拿数据库现有模板兜底判断，避免误伤只改时间/备注的请求。
        """
        from app.utils.activity import requires_template

        fields = self.model_fields_set
        if "template_id" in fields and "activity_type" in fields:
            if self.template_id is None and requires_template(self.activity_type):
                raise ValueError("请选择检查模板（检查类审核活动必须绑定检查模板）")
        return self


class AuditPlanItemResponse(AuditPlanItemBase):
    """审核计划项响应"""
    id: UUID
    project_id: UUID
    inspection_task_id: Optional[UUID] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


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


class AuditAreaRecordCreate(AuditAreaRecordBase):
    """创建审核区域记录（完整字段，用于内部调用）"""
    project_id: UUID = Field(..., description="所属审核项目 ID")
    recorded_by: UUID = Field(..., description="主填写人 ID")


class AuditAreaRecordItemPayload(BaseModel):
    """区域记录检查项批量保存的单条载荷。

    定位方式：优先 id（既有记录项），其次 template_item_id（按模板项匹配，
    不存在则创建）。其余字段「给出即写入」，未给出的字段保持原值。
    """
    id: Optional[UUID] = None
    template_item_id: Optional[UUID] = None
    ensure_exists: bool = Field(False, description="上传附件前显式创建空明细")
    result: Optional[str] = None
    radio_value: Optional[str] = None
    evaluation_3level: Optional[str] = None
    score_value: Optional[str] = None
    numeric_value: Optional[str] = None
    text_value: Optional[str] = None
    multi_value: Optional[List[str]] = None
    audit_evidence: Optional[str] = None
    audit_findings: Optional[str] = None
    rectification_suggestion: Optional[str] = None
    inspector_note: Optional[str] = None
    photos: Optional[List[str]] = None

    @field_validator("result", "radio_value", "evaluation_3level", mode="before")
    @classmethod
    def _normalize_verdict(cls, value):
        if value is None:
            return None
        value = str(value).strip()
        return None if not value or value.lower() == "null" else value

    def normalized_updates(self) -> dict:
        """非空结论按 radio → result → 三级评价取值；全部显式为空才清空。

        客户端可能同时发送旧评价和新选择，优先级固定，不能让旧字段的 null
        遮住新选择。三级评价 2 与 pass 一致时保留其「基本符合」含义。
        """
        from app.utils.item_stats import classify_result_ext

        data = self.model_dump(exclude_unset=True)
        verdict_fields = ("radio_value", "result", "evaluation_3level")
        if not any(field in data for field in verdict_fields):
            return data
        selected = next((field for field in verdict_fields if data.get(field) is not None), None)
        if selected is None:
            data.update(dict.fromkeys(verdict_fields))
            return data

        value = data[selected]
        if selected == "evaluation_3level":
            evaluation = value
            result = "fail" if value == "3" else "pass"
        else:
            bucket = classify_result_ext(value)
            result = bucket or value
            evaluation = {"pass": "1", "fail": "3"}.get(bucket)
            if value == "pending_rectification":
                evaluation = "3"
            elif bucket == "observe":
                evaluation = "2"
            if bucket == "pass" and data.get("evaluation_3level") == "2":
                evaluation = "2"
        data.update(radio_value=result, result=result, evaluation_3level=evaluation)
        return data

    @field_validator("evaluation_3level")
    @classmethod
    def _validate_evaluation(cls, value):
        if value is not None and value not in {"1", "2", "3"}:
            raise ValueError("三级评价必须为 1、2 或 3")
        return value

    @field_validator("score_value", "numeric_value", mode="before")
    @classmethod
    def _stringify_number(cls, value):
        # 列类型是 String；前端 stepper/输入框可能提交数字，统一转字符串落库
        if value is None:
            return None
        return str(value)


class AuditAreaRecordItemsUpdate(BaseModel):
    """批量保存区域记录检查项"""
    items: List[AuditAreaRecordItemPayload]


class AuditAreaRecordRequest(AuditAreaRecordBase):
    """表头、明细及提交状态在一个事务中创建。"""
    items: List[AuditAreaRecordItemPayload] = Field(default_factory=list)
    status: Literal["draft", "in_progress", "submitted"] = "draft"


class AuditAreaRecordUpdate(BaseModel):
    """更新审核区域记录，可携带明细原子提交。"""
    area_id: Optional[UUID] = None
    template_id: Optional[UUID] = None
    certification_systems: Optional[List[str]] = None
    co_recorders: Optional[List[UUID]] = None
    audit_date: Optional[date] = None
    audit_time_start: Optional[str] = None
    audit_time_end: Optional[str] = None
    conclusion: Optional[str] = None
    status: Optional[Literal["draft", "in_progress", "submitted"]] = None
    items: Optional[List[AuditAreaRecordItemPayload]] = None


class AuditAreaRecordResponse(AuditAreaRecordBase):
    """审核区域记录响应"""
    id: UUID
    project_id: UUID
    record_no: Optional[str] = None
    recorded_by: UUID
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
    source_draft_id: Optional[UUID] = None
    confirmed_by: Optional[UUID] = None
    confirmed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
    """创建审核报告

    project_id 可选：以 URL 路径中的 project_id 为准（BUG-36）。
    传入时若与路径不一致将返回 422。
    """
    model_config = ConfigDict(extra="forbid")
    project_id: Optional[UUID] = Field(None, description="所属审核项目 ID（可选，默认取路径参数）")


class AuditReportUpdate(BaseModel):
    """更新审核报告"""
    model_config = ConfigDict(extra="forbid")
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
    consistency_check: dict = Field(default_factory=dict)
    completeness_check: dict = Field(default_factory=dict)
    source_snapshot: dict = Field(default_factory=dict)
    version: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
    """创建沟通会议

    project_id 可选：以 URL 路径中的 project_id 为准（BUG-36）。
    传入时若与路径不一致将返回 422。
    """
    project_id: Optional[UUID] = Field(None, description="所属审核项目 ID（可选，默认取路径参数）")


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

    model_config = ConfigDict(from_attributes=True)


class AiNcSuggestRequest(BaseModel):
    """AI 不符合项建议请求体"""
    evidence: Optional[str] = Field(None, description="审核现场证据")
    clause_no: Optional[str] = Field(None, description="标准条款号")
    certification_system: Optional[str] = Field(None, description="认证体系代码")


class AiEvidenceEvaluationRequest(BaseModel):
    """AI 证据评估请求体"""
    evidence: Optional[str] = Field(None, description="审核现场证据")
    clause_no: Optional[str] = Field(None, description="标准条款号")
    certification_system: Optional[str] = Field(None, description="认证体系代码")
