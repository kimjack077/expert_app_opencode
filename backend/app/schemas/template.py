from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from uuid import UUID
from decimal import Decimal


class TemplateItemBase(BaseModel):
    """检查项目基础模型"""
    title: str = Field(..., max_length=500, description="检查项目标题")
    parent_id: Optional[UUID] = Field(None, description="父项目 ID")
    description: Optional[str] = Field(None, description="检查项目描述")
    check_method: Optional[str] = Field(None, description="检查方法")
    legal_basis: Optional[str] = Field(None, description="法律依据")
    standard_ref: Optional[str] = Field(None, max_length=200, description="标准依据")

    # 检查结论配置
    # check_type 支持: score(打分)/radio(单选)/numeric(数值)/text(文本)/multi_check(多选)
    check_type: Optional[str] = Field("radio", description="检查类型：score/radio/numeric/text/multi_check")
    # 兼容旧字段
    result_type: Optional[str] = Field("pass_fail", description="结论类型：pass_fail/numeric/text（已废弃）")
    result_options: Optional[Any] = Field(None, description="结论选项（用于 radio/multi_check）")
    # 数值类型配置
    min_value: Optional[Decimal] = Field(None, description="数值类型最小值")
    max_value: Optional[Decimal] = Field(None, description="数值类型最大值")
    unit: Optional[str] = Field(None, max_length=50, description="数值单位")
    # 打分类型配置
    max_score: Optional[Decimal] = Field(None, description="打分类型最大分数")
    score_step: Optional[Decimal] = Field(None, description="打分步长")
    pass_score: Optional[Decimal] = Field(None, description="合格分数线")

    # 其他配置
    is_required: Optional[bool] = Field(True, description="是否必填")
    use_ai: Optional[bool] = Field(False, description="是否使用AI")
    risk_level: Optional[str] = Field("medium", description="风险等级")
    sort_order: Optional[int] = Field(0, description="排序")
    is_category: Optional[bool] = Field(False, description="是否为分类节点")

    # 新增量化和AI配置
    score_weight: Optional[Decimal] = Field(None, description="权重")
    default_score: Optional[Decimal] = Field(None, description="默认分数")
    allow_attachment: Optional[bool] = Field(False, description="是否允许附件")
    attachment_required: Optional[bool] = Field(False, description="附件是否必须")
    ai_prompt_template: Optional[str] = Field(None, description="AI提示词模板")


class TemplateItemCreate(TemplateItemBase):
    """创建检查项目"""
    pass


class TemplateItemUpdate(BaseModel):
    """更新检查项目"""
    parent_id: Optional[UUID] = None
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    check_method: Optional[str] = None
    legal_basis: Optional[str] = None
    standard_ref: Optional[str] = None
    check_type: Optional[str] = None
    result_type: Optional[str] = None
    result_options: Optional[Any] = None
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    unit: Optional[str] = None
    max_score: Optional[Decimal] = None
    score_step: Optional[Decimal] = None
    pass_score: Optional[Decimal] = None
    is_required: Optional[bool] = None
    use_ai: Optional[bool] = None
    risk_level: Optional[str] = None
    sort_order: Optional[int] = None
    is_category: Optional[bool] = None
    score_weight: Optional[Decimal] = None
    default_score: Optional[Decimal] = None
    allow_attachment: Optional[bool] = None
    attachment_required: Optional[bool] = None
    ai_prompt_template: Optional[str] = None


class TemplateItemResponse(TemplateItemBase):
    """检查项目响应"""
    id: UUID
    template_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InspectionTemplateBase(BaseModel):
    """检查模板基础模型"""
    name: str = Field(..., max_length=200, description="模板名称")
    code: Optional[str] = Field(None, max_length=50, description="模板编码")
    description: Optional[str] = Field(None, description="模板描述")
    category: Optional[str] = Field(None, max_length=100, description="模板类别")
    version: Optional[str] = Field("1.0", description="版本号")
    is_quantified: Optional[bool] = Field(False, description="是否量化")
    is_public: Optional[bool] = Field(False, description="是否公共模板")


class InspectionTemplateCreate(InspectionTemplateBase):
    """创建检查模板"""
    pass


class InspectionTemplateUpdate(BaseModel):
    """更新检查模板"""
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    version: Optional[str] = None
    is_published: Optional[bool] = None
    is_public: Optional[bool] = None
    is_quantified: Optional[bool] = None


class InspectionTemplateResponse(InspectionTemplateBase):
    """检查模板响应"""
    id: UUID
    is_published: bool
    is_public: bool
    is_quantified: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InspectionTemplateDetail(InspectionTemplateResponse):
    """检查模板详情（包含检查项目）"""
    items: List[dict] = []
