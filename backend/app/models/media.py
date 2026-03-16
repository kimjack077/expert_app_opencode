from sqlalchemy import Column, String, DateTime, ForeignKey, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from ..database import Base


class MediaFile(Base):
    __tablename__ = "media_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("inspection_tasks.id"))
    record_id = Column(UUID(as_uuid=True), ForeignKey("task_item_records.id"))
    file_type = Column(String(20), default="image")
    original_name = Column(String(255))
    stored_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(BigInteger)
    mime_type = Column(String(100))
    thumbnail_path = Column(String(500))
    lat = Column(String(50))
    lng = Column(String(50))
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    record = relationship("TaskItemRecord", back_populates="media_files")
