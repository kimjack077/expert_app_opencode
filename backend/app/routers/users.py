from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.schemas.common import ApiResponse
from app.utils.security import get_current_user, get_password_hash, get_current_admin_user

router = APIRouter()

def make_response(data=None, code=200, message="success"):
    return ApiResponse(
        code=code, message=message, data=data, timestamp=datetime.utcnow()
    )

@router.get("/", response_model=ApiResponse)
async def get_users(
    skip: int = 0,
    limit: int = 100,
    role: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    query = select(User)
    if role:
        query = query.where(User.role == role)
        
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()
    
    return make_response(data=[UserResponse.model_validate(u).model_dump() for u in users])

@router.get("/{user_id}", response_model=ApiResponse)
async def get_user(
    user_id: UUID, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return make_response(data=UserResponse.model_validate(user).model_dump())

@router.post("/", response_model=ApiResponse)
async def create_user(
    data: UserCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")
        
    user_data = data.model_dump()
    password = user_data.pop("password")
    user_data["hashed_password"] = get_password_hash(password)
    
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
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    update_data = data.model_dump(exclude_unset=True)
    
    if "username" in update_data and update_data["username"] != user.username:
        result = await db.execute(select(User).where(User.username == update_data["username"]))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Username already exists")

    if "password" in update_data:
        password = update_data.pop("password")
        user.hashed_password = get_password_hash(password)
        
    for key, value in update_data.items():
        setattr(user, key, value)
        
    await db.commit()
    await db.refresh(user)
    return make_response(data=UserResponse.model_validate(user).model_dump())

@router.delete("/{user_id}", response_model=ApiResponse)
async def delete_user(
    user_id: UUID, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    await db.delete(user)
    await db.commit()
    return make_response(message="User deleted successfully")
