from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from ..database import Base


class InspectionTask(Base):
    __tablename__ = "inspection_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_no = Column(String(50), unique=True, nullable=False)
    title = Column(String(300), nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey("inspection_templates.id"))
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    target_name = Column(String(200))
    target_address = Column(String(500))
    target_contact = Column(String(100))
    target_phone = Column(String(20))
    scheduled_at = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    status = Column(String(20), default="pending")
    remarks = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    template = relationship("InspectionTemplate")
    assignee = relationship("User", foreign_keys=[assigned_to])
    assigner = relationship("User", foreign_keys=[assigned_by])
    records = relationship(
        "TaskItemRecord", back_populates="task", cascade="all, delete-orphan"
    )


class TaskItemRecord(Base):
    """检查任务中的项目记录"""
    __tablename__ = "task_item_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("inspection_tasks.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属任务 ID"
    )
    template_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("template_items.id"),
        comment="模板项目 ID"
    )
    result = Column(String(20), comment="检查结果：pass/fail 等")
    result_value = Column(String(50), comment="数值结果")
    result_text = Column(Text, comment="文字结论")
    inspector_note = Column(Text, comment="检查员备注")
    llm_suggestion = Column(Text, comment="AI 建议")
    llm_basis = Column(Text, comment="AI 依据")
    recorded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    task = relationship("InspectionTask", back_populates="records")
    template_item = relationship("TemplateItem", back_populates="task_records")
    media_files = relationship("MediaFile", back_populates="record", cascade="all, delete-orphan")
