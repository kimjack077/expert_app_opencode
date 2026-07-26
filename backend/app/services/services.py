from datetime import datetime, timezone
from typing import Optional, List
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.user import User, Organization
from app.models.task import InspectionTask, TaskItemRecord
from app.models.template import (
    InspectionTemplate,
    TemplateItem,
)
from app.models.audit import AuditLog
from app.utils.security import get_password_hash


class AuditService:
    @staticmethod
    async def log_action(
        db: AsyncSession,
        user_id: Optional[str],
        username: Optional[str],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        detail: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        try:
            log = AuditLog(
                user_id=user_id,
                username=username,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                detail=detail,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            db.add(log)
            await db.flush()  # Use flush instead of commit to avoid finishing transactions early in middleware
        except Exception as e:
            # No rollback needed for flush if we handle the error
            print(f"Audit log failed: {e}")


class UserService:
    @staticmethod
    async def create_user(
        db: AsyncSession,
        username: str,
        password: str,
        role: str = "expert",
        email: Optional[str] = None,
        full_name: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> User:
        user = User(
            username=username,
            hashed_password=get_password_hash(password),
            role=role,
            email=email,
            full_name=full_name,
            org_id=org_id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def get_by_username(db: AsyncSession, username: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()


class TaskService:
    @staticmethod
    async def create_task(
        db: AsyncSession,
        title: str,
        template_id: Optional[str],
        assigned_to: Optional[str],
        assigned_by: str,
        target_name: Optional[str] = None,
        target_address: Optional[str] = None,
        scheduled_at: Optional[datetime] = None,
    ) -> InspectionTask:
        # 同 routers/tasks.py：count(*)+1 并发会撞号，改用随机短码
        task_no = f"TASK-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"

        task = InspectionTask(
            task_no=task_no,
            title=title,
            template_id=template_id,
            assigned_to=assigned_to,
            assigned_by=assigned_by,
            target_name=target_name,
            target_address=target_address,
            scheduled_at=scheduled_at,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        if template_id:
            await TaskService._create_records_from_template(db, task)

        return task

    @staticmethod
    async def _create_records_from_template(db: AsyncSession, task: InspectionTask):
        result = await db.execute(
            select(TemplateItem)
            .where(TemplateItem.template_id == task.template_id)
            .order_by(TemplateItem.sort_order)
        )
        items = result.scalars().all()

        for item in items:
            record = TaskItemRecord(
                task_id=task.id,
                template_item_id=item.id,
            )
            db.add(record)
        await db.commit()

    @staticmethod
    async def get_user_tasks(db: AsyncSession, user_id: str) -> List[InspectionTask]:
        result = await db.execute(
            select(InspectionTask)
            .where(InspectionTask.assigned_to == user_id)
            .order_by(InspectionTask.created_at.desc())
        )
        return result.scalars().all()

    @staticmethod
    async def get_task_records(
        db: AsyncSession, task_id: str
    ) -> List[TaskItemRecord]:
        result = await db.execute(
            select(TaskItemRecord)
            .options(selectinload(TaskItemRecord.template_item))
            .where(TaskItemRecord.task_id == task_id)
            .order_by(TaskItemRecord.recorded_at)
        )
        return result.scalars().all()
