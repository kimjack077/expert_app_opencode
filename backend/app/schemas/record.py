from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Literal, Optional, List
from datetime import datetime
from uuid import UUID
from decimal import Decimal

# 检查结论枚举（与 schemas/task.py 的 CheckResult 保持一致）
CheckResult = Literal["pass", "fail", "na", "not_applicable"]


class InspectionRecordBase(BaseModel):
    template_id: UUID = Field(..., description="使用的检查模板 ID")
    enterprise_id: Optional[UUID] = Field(None, description="被检查企业 ID")
    enterprise_name: Optional[str] = Field(None, max_length=200, description="企业名称（手动输入）")
    enterprise_address: Optional[str] = Field(None, max_length=500, description="企业地址（手动输入）")
    contact_person: Optional[str] = Field(None, max_length=100, description="联系人（手动输入）")
    contact_phone: Optional[str] = Field(None, max_length=20, description="联系电话（手动输入）")
    inspection_date: Optional[datetime] = Field(None, description="检查时间")
    remarks: Optional[str] = Field(None, description="备注")
    judgment_note: Optional[str] = Field(None, description="判定说明")
    total_score: Optional[Decimal] = Field(None, description="检查总分")


class InspectionRecordCreate(InspectionRecordBase):
    pass


class InspectionRecordUpdate(BaseModel):
    enterprise_id: Optional[UUID] = None
    enterprise_name: Optional[str] = None
    enterprise_address: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    inspection_date: Optional[datetime] = None
    remarks: Optional[str] = None
    judgment_note: Optional[str] = None
    overall_result: Optional[str] = None
    status: Optional[str] = None
    total_score: Optional[Decimal] = None


class InspectionRecordResponse(InspectionRecordBase):
    id: UUID
    inspector_id: UUID
    status: str
    overall_result: Optional[str]
    judgment_note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InspectionRecordDetail(InspectionRecordResponse):
    template: Optional[dict] = None
    enterprise: Optional[dict] = None
    inspector: Optional[dict] = None
    items: List["InspectionRecordItemResponse"] = []


class InspectionRecordItemBase(BaseModel):
    id: Optional[UUID] = Field(None, description="记录项 ID（用于更新已有记录）")
    template_item_id: Optional[UUID] = Field(None, description="模板检查项 ID")
    title: Optional[str] = Field(None, description="检查项标题")
    description: Optional[str] = Field(None, description="检查项描述")
    check_method: Optional[str] = Field(None, description="检查方法")
    legal_basis: Optional[str] = Field(None, description="法律依据")
    standard_ref: Optional[str] = Field(None, description="标准编号")
    risk_level: Optional[str] = Field(None, description="风险等级")
    check_type: Optional[str] = Field(None, description="检查类型")
    result_type: Optional[str] = Field(None, description="结果类型")
    result_options: Optional[dict] = Field(None, description="选项配置")
    min_value: Optional[float] = Field(None, description="最小值")
    max_value: Optional[float] = Field(None, description="最大值")
    unit: Optional[str] = Field(None, description="单位")
    is_required: Optional[bool] = Field(True, description="是否必填")
    use_ai: Optional[bool] = Field(False, description="是否使用AI")
    ai_prompt_template: Optional[str] = Field(None, description="AI提示词模板")
    # 通用结果字段（保留兼容）
    result: Optional[CheckResult] = Field(None, description="检查结果：pass/fail/na")
    result_value: Optional[str] = Field(None, max_length=50, description="数值结果")
    result_text: Optional[str] = Field(None, description="文字结论")
    # 新增：按检查类型存储结果
    score_value: Optional[str] = Field(None, description="打分类型结果")
    radio_value: Optional[str] = Field(None, description="单选类型结果")
    multi_value: Optional[List[str]] = Field(None, description="多选类型结果列表")
    numeric_value: Optional[str] = Field(None, description="数值类型结果")
    text_value: Optional[str] = Field(None, description="文本类型结果")
    # AI 相关
    ai_generated: Optional[bool] = Field(False, description="是否为AI生成")
    ai_suggestion: Optional[str] = Field(None, description="AI建议内容")
    ai_basis: Optional[str] = Field(None, description="AI法规依据")
    # 问题描述和整改建议
    problem_description: Optional[str] = Field(None, description="问题描述")
    rectification_suggestion: Optional[str] = Field(None, description="整改建议")
    # 其他
    inspector_note: Optional[str] = Field(None, description="检查员备注")
    photos: Optional[List[str]] = Field(None, description="照片 URL 列表")


class InspectionRecordItemCreate(InspectionRecordItemBase):
    pass


class InspectionRecordItemUpdate(BaseModel):
    result: Optional[CheckResult] = None
    result_value: Optional[str] = None
    result_text: Optional[str] = None
    score_value: Optional[str] = None
    radio_value: Optional[str] = None
    multi_value: Optional[List[str]] = None
    numeric_value: Optional[str] = None
    text_value: Optional[str] = None
    ai_generated: Optional[bool] = None
    ai_suggestion: Optional[str] = None
    ai_basis: Optional[str] = None
    problem_description: Optional[str] = None
    rectification_suggestion: Optional[str] = None
    inspector_note: Optional[str] = None
    photos: Optional[List[str]] = None


class InspectionRecordItemCorrection(InspectionRecordItemUpdate):
    """管理员更正已提交记录条目时的请求体。"""

    @field_validator("score_value", "numeric_value", mode="before")
    @classmethod
    def serialize_number(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float, Decimal)):
            if not Decimal(str(value)).is_finite():
                raise ValueError("数值必须为有限数字")
            return str(value)
        return value

    reason: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="更正原因（写入审计日志）",
    )


class InspectionRecordItemResponse(InspectionRecordItemBase):
    id: UUID
    record_id: UUID
    recorded_at: datetime
    updated_at: datetime
    # 响应层放宽为 str：兼容历史脏数据（空串等），避免序列化 500
    result: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InspectionRecordListQuery(BaseModel):
    template_id: Optional[UUID] = None
    enterprise_id: Optional[UUID] = None
    inspector_id: Optional[UUID] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    skip: int = Field(0, ge=0)
    limit: int = Field(20, ge=1, le=100)
