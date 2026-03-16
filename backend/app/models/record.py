from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, JSON, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from ..database import Base


class InspectionRecord(Base):
    """检查记录 - 主表（简化版，不需要任务）"""
    __tablename__ = "inspection_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 模板关联
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("inspection_templates.id"),
        nullable=False,
        comment="使用的检查模板 ID"
    )
    
    # 企业关联（可选，支持手动输入企业信息）
    enterprise_id = Column(
        UUID(as_uuid=True),
        ForeignKey("enterprises.id"),
        comment="被检查企业 ID（可选）"
    )
    
    # 手动输入的企业信息（如果没有选择企业）
    enterprise_name = Column(String(200), comment="企业名称（手动输入）")
    enterprise_address = Column(String(500), comment="企业地址（手动输入）")
    contact_person = Column(String(100), comment="联系人（手动输入）")
    contact_phone = Column(String(20), comment="联系电话（手动输入）")
    
    # 检查员
    inspector_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        comment="检查员 ID"
    )
    
    # 检查时间
    inspection_date = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="检查时间"
    )
    
    # 状态和结果
    status = Column(String(20), default="draft", comment="状态：draft/submitted")
    overall_result = Column(String(20), comment="总体结论")
    total_score = Column(Numeric, comment="检查总分")
    remarks = Column(Text, comment="备注")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 模板快照（创建记录时保存完整模板结构，防止模板变更影响历史记录）
    template_snapshot = Column(JSON, comment="创建检查记录时的模板快照 JSON")

    # 关联关系
    template = relationship("InspectionTemplate")
    enterprise = relationship("Enterprise")
    inspector = relationship("User")
    items = relationship(
        "InspectionRecordItem",
        back_populates="record",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<InspectionRecord {self.id}>"


class InspectionRecordItem(Base):
    """检查记录项 - 具体检查项目的结果"""
    __tablename__ = "inspection_record_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 关联记录
    record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("inspection_records.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属检查记录 ID"
    )
    
    # 关联模板检查项
    template_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("template_items.id"),
        comment="模板检查项 ID"
    )
    
    # 检查结果
    # 通用结果字段（保留兼容）
    result = Column(String(20), comment="检查结果：pass/fail")
    result_value = Column(String(50), comment="数值结果")
    result_text = Column(Text, comment="文字结论")

    # 新增：按检查类型存储结果
    score_value = Column(String(20), comment="打分类型结果")
    radio_value = Column(String(100), comment="单选类型结果")
    multi_value = Column(JSON, default=list, comment="多选类型结果列表")
    numeric_value = Column(String(50), comment="数值类型结果")
    text_value = Column(Text, comment="文本类型结果")

    # 问题描述和整改建议
    problem_description = Column(Text, comment="问题描述（发现的问题）")
    rectification_suggestion = Column(Text, comment="整改建议")

    # AI 辅助相关
    ai_generated = Column(Boolean, default=False, comment="是否为AI生成")
    ai_suggestion = Column(Text, comment="AI建议内容")
    ai_basis = Column(Text, comment="AI法规依据")

    inspector_note = Column(Text, comment="检查员备注")
    
    # 照片（存储 URL 列表）
    photos = Column(JSON, default=list, comment="照片 URL 列表")

    # ─── 冗余快照字段（创建时从模板项复制，保证历史不断链） ───
    item_title          = Column(String(500), comment="快照：检查项标题")
    item_description    = Column(Text, comment="快照：检查项描述")
    item_check_method   = Column(Text, comment="快照：检查方法")
    item_legal_basis    = Column(Text, comment="快照：法律依据")
    item_standard_ref   = Column(Text, comment="快照：标准编号")
    item_risk_level     = Column(String(20), comment="快照：风险等级")
    item_check_type     = Column(String(50), comment="快照：检查类型")
    item_result_options = Column(JSON, comment="快照：选项配置")
    item_min_value      = Column(Numeric, comment="快照：最小值")
    item_max_value      = Column(Numeric, comment="快照：最大值")
    item_unit           = Column(String(50), comment="快照：单位")
    item_score_weight   = Column(Numeric, comment="快照：权重")
    item_default_score  = Column(Numeric, comment="快照：默认分数")
    item_allow_attachment = Column(Boolean, comment="快照：是否允许附件")
    item_attachment_required = Column(Boolean, comment="快照：附件是否必选")
    item_ai_prompt_template = Column(Text, comment="快照：AI提示词")
    item_use_ai = Column(Boolean, default=False, comment="快照：是否使用AI")
    # ────────────────────────────────────────────────────────────
    
    # 时间戳
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # 关联关系
    record = relationship("InspectionRecord", back_populates="items")
    template_item = relationship("TemplateItem")

    def __repr__(self):
        return f"<InspectionRecordItem {self.id}>"
