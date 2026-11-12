from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.schemas.common import ApiResponse
from app.utils.security import (
    get_current_user,
    get_password_hash_async,
    get_current_admin_user,
    invalidate_user_cache,
)
from app.utils.response import make_response
from app.utils.roles import is_admin
from app.services.project_access_service import ensure_project_access

router = APIRouter()


@router.get("", response_model=ApiResponse)
async def get_users(
    skip: int = 0,
    limit: int = 100,
    role: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    query = select(User).where(User.is_deleted == False)  # noqa: E712
    if role:
        query = query.where(User.role == role)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()

    return make_response(data=[UserResponse.model_validate(u).model_dump() for u in users])


@router.get("/options", response_model=ApiResponse)
async def get_user_options(
    role: Optional[str] = None,
    project_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """轻量成员列表 —— 供任务分配 / 审核组选员下拉使用。

    GET /users 仅管理员可用，expert/组长打开分配下拉会静默 403、列表为空。
    管理员可选员；项目负责人须提供其管理的项目，其他用户无权枚举通讯录。
    """
    if not is_admin(current_user.role):
        if not project_id:
            raise HTTPException(status_code=403, detail="仅管理员或项目负责人可选择成员")
        await ensure_project_access(db, project_id, current_user, require_manage=True)
    query = select(User).where(
        User.is_deleted == False,  # noqa: E712
        User.is_active == True,  # noqa: E712
    )
    if role:
        query = query.where(User.role == role)
    query = query.order_by(User.full_name, User.username).limit(500)
    result = await db.execute(query)
    users = result.scalars().all()
    return make_response(
        data=[
            {
                "id": str(u.id),
                "username": u.username,
                "full_name": u.full_name,
                "role": u.role,
            }
            for u in users
        ]
    )


@router.get("/{user_id}", response_model=ApiResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    try:
        parsed_user_id = UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    user = await db.get(User, parsed_user_id)
    if not user or user.is_deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return make_response(data=UserResponse.model_validate(user).model_dump())

@router.post("", response_model=ApiResponse)
async def create_user(
    data: UserCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already exists")
        
    user_data = data.model_dump()
    password = user_data.pop("password")
    user_data["hashed_password"] = await get_password_hash_async(password)
    
    user = User(**user_data)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return make_response(data=UserResponse.model_validate(user).model_dump())

@router.put("/{user_id}", response_model=ApiResponse)
async def update_user(
    user_id: UUID, 
    data: UserUpdate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    user = await db.get(User, user_id)
    if not user or user.is_deleted:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = data.model_dump(exclude_unset=True)

    old_username = user.username
    if "username" in update_data and update_data["username"] != user.username:
        result = await db.execute(select(User).where(User.username == update_data["username"]))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Username already exists")

    if "password" in update_data:
        password = update_data.pop("password")
        user.hashed_password = await get_password_hash_async(password)

    for key, value in update_data.items():
        setattr(user, key, value)

    await db.commit()
    await db.refresh(user)
    # 角色/停用/改名/改密等变更需立刻反映到鉴权缓存（新旧用户名都要失效）
    invalidate_user_cache(old_username)
    if user.username != old_username:
        invalidate_user_cache(user.username)
    return make_response(data=UserResponse.model_validate(user).model_dump())

@router.delete("/{user_id}", response_model=ApiResponse)
async def delete_user(
    user_id: UUID, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    user = await db.get(User, user_id)
    if not user or user.is_deleted:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")

    if user.role == "super_admin":
        from sqlalchemy import func

        active_super_admins = await db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.role == "super_admin",
                User.is_deleted == False,  # noqa: E712
                User.is_active == True,  # noqa: E712
            )
        )
        if active_super_admins <= 1:
            raise HTTPException(status_code=400, detail="不能删除最后一个超级管理员")

    from app.utils.soft_delete import soft_delete

    old_username = user.username
    user.is_active = False
    await soft_delete(db, user, unique_fields=["username", "email"])
    await db.commit()
    # 软删除改名（追加 _deleted_ 后缀），新旧用户名都失效，避免缓存继续放行
    invalidate_user_cache(old_username)
    invalidate_user_cache(user.username)
    return make_response(message="User deleted successfully")
