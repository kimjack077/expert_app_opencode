from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Integer,
    ARRAY,
    JSON,
    Numeric,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from ..database import Base
from .base import SoftDeleteMixin


class InspectionTemplate(Base, SoftDeleteMixin):
    """检查模板 - 主表"""
    __tablename__ = "inspection_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False, comment="模板名称，如：食品安全检查模板")
    code = Column(String(50), unique=True, comment="模板编码")
    description = Column(Text, comment="模板描述")
    category = Column(String(100), comment="模板类别，如：食品安全、安全生产")
    industry_id = Column(UUID(as_uuid=True), ForeignKey("industries.id", ondelete="SET NULL"), nullable=True)
    version = Column(String(20), default="1.0", comment="版本号")
    
    # 认证审核专用字段（新增）
    certification_system = Column(
        String(20),
        comment="适用认证体系：Q(质量)/E(环境)/S(职业健康安全)/En(能源)/QES/QESEn"
    )
    applicable_area_type = Column(
        String(100),
        comment="适用区域类型：高层领导/车间/职能部门/通用"
    )
    is_published = Column(Boolean, default=False, comment="是否已发布")
    is_public = Column(Boolean, default=False, comment="是否公共模板（公共模板所有专家可见，个人模板仅创建者可见）")
    is_quantified = Column(Boolean, default=False, comment="是否量化")
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    items = relationship(
        "TemplateItem", 
        back_populates="template", 
        cascade="all, delete-orphan",
        order_by="TemplateItem.sort_order"
    )
    industry = relationship("Industry")

    def __repr__(self):
        return f"<InspectionTemplate {self.name}>"


class TemplateItem(Base, SoftDeleteMixin):
    """检查项目 - 支持层级结构"""
    __tablename__ = "template_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("inspection_templates.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属模板 ID"
    )
    parent_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("template_items.id"),
        comment="父项目 ID，用于构建层级"
    )
    title = Column(String(500), nullable=False, comment="检查项目标题")
    description = Column(Text, comment="检查项目描述")
    check_method = Column(Text, comment="检查方法")
    legal_basis = Column(Text, comment="法律依据")
    standard_ref = Column(String(200), comment="标准依据")
    
    # 认证审核专用字段（新增）
    clause_no = Column(
        String(50),
        comment="标准条款号，如 '8.5.1' 或 '6.1.2'"
    )
    applicable_systems = Column(
        JSON,
        default=list,
        comment="适用体系列表，如 ['Q', 'E', 'S']"
    )
    evidence_hint = Column(
        Text,
        comment="审核员填写提示（应查什么证据）"
    )
    
    # 检查结论配置
    # check_type 支持: score(打分)/radio(单选)/numeric(数值)/text(文本)/multi_check(多选)/audit_3level(审核三级评估)
    check_type = Column(String(20), default="radio", comment="检查类型：score/radio/numeric/text/multi_check/audit_3level")
    # 旧字段兼容
    result_type = Column(String(20), default="pass_fail", comment="结论类型：pass_fail/numeric/text（已废弃，使用check_type）")
    result_options = Column(JSON, comment="结论选项，用于 radio/multi_check 类型的选项配置")
    # 数值类型配置
    min_value = Column(Numeric, comment="数值类型最小值")
    max_value = Column(Numeric, comment="数值类型最大值")
    unit = Column(String(50), comment="数值单位")
    # 打分类型配置
    max_score = Column(Numeric, comment="打分类型最大分数")
    score_step = Column(Numeric, comment="打分步长")
    pass_score = Column(Numeric, comment="合格分数线")
    
    # 其他配置
    is_required = Column(Boolean, default=True, comment="是否必填")
    use_ai = Column(Boolean, default=False, comment="是否使用AI")
    risk_level = Column(String(20), default="medium", comment="风险等级")
    sort_order = Column(Integer, default=0, comment="排序")
    tags = Column(ARRAY(Text), comment="标签")
    is_category = Column(Boolean, default=False, comment="是否为分类节点")
    
    # 新增量化和AI配置
    score_weight = Column(Numeric, comment="权重")
    default_score = Column(Numeric, comment="默认分数")
    allow_attachment = Column(Boolean, default=False, comment="是否允许附件")
    attachment_required = Column(Boolean, default=False, comment="附件是否必须")
    ai_prompt_template = Column(Text, comment="AI提示词模板")
    
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 自关联，支持层级
    parent = relationship(
        "TemplateItem", 
        remote_side=[id],
        backref="children"
    )
    template = relationship("InspectionTemplate", back_populates="items")
    task_records = relationship("TaskItemRecord", back_populates="template_item")

    def __repr__(self):
        return f"<TemplateItem {self.title}>"
