"""软删除工具函数"""
from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def soft_delete(
    db: AsyncSession,
    obj,
    unique_fields: Optional[Iterable[str]] = None,
) -> None:
    """对对象执行软删除。

    - 设置 is_deleted=True, deleted_at=now
    - 对 unique_fields 中的字段追加 _deleted_<timestamp> 后缀，
      避免软删除记录阻塞新记录的创建（唯一约束冲突）。

    Args:
        db: 异步会话
        obj: ORM 对象（需具备 is_deleted / deleted_at 字段）
        unique_fields: 需要重命名的唯一字段列表，如 ['username', 'email']
    """
    obj.is_deleted = True
    obj.deleted_at = datetime.now(timezone.utc)

    if unique_fields:
        suffix = f"_deleted_{int(datetime.now(timezone.utc).timestamp())}"
        for field_name in unique_fields:
            current = getattr(obj, field_name, None)
            if current and isinstance(current, str) and not current.endswith("_deleted"):
                # 截断以避免超过字段长度限制
                max_len = 200  # 保守限制
                new_val = (current + suffix)
                if len(new_val) > max_len:
                    new_val = current[: max_len - len(suffix)] + suffix
                setattr(obj, field_name, new_val)

    await db.flush()


def not_deleted(model):
    """返回 model.is_deleted == False 的过滤条件，用于 query.where(not_deleted(Model))"""
    return model.is_deleted == False  # noqa: E712
