from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Numeric,
    Integer,
    BigInteger,
    ARRAY,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from ..database import Base


class SoftDeleteMixin:
    """软删除 Mixin：为模型添加 is_deleted / deleted_at 字段。

    使用方式：
        class MyModel(Base, SoftDeleteMixin):
            ...

    约定：
    - DELETE 接口将 is_deleted=True, deleted_at=now()，并保留原始数据
    - 所有 list/get 查询需过滤 is_deleted == False
    - 软删除时，对唯一字段（username/code/email）追加后缀以避免阻塞新记录创建
    """

    is_deleted = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="是否软删除",
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="软删除时间",
    )


class BaseModel(Base):
    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

