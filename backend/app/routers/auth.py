from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Body, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.schemas import (
    Token,
    UserCreate,
    UserResponse,
    LoginRequest,
    ChangePasswordRequest,
    ApiResponse,
)
from app.utils.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    _token_revoked,
    get_current_user,
)
from app.services import AuditService

router = APIRouter()

# 公开自注册端点强制使用的角色。绝不使用客户端传入的 role。
SELF_REGISTRATION_ROLE = "expert"


def make_response(data=None, code=200, message="success"):
    return ApiResponse(
        code=code, message=message, data=data, timestamp=datetime.now(timezone.utc)
    )


@router.post("/login", response_model=ApiResponse)
async def login(
    request: Request, login_data: LoginRequest, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.username == login_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="User account is disabled")

    token_data = {
        "sub": user.username,
        "rv": user.token_revoked_at.isoformat() if user.token_revoked_at else None,
    }
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    return make_response(
        data={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": UserResponse.model_validate(user).model_dump(),
        }
    )


@router.post("/logout", response_model=ApiResponse)
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current_user.token_revoked_at = datetime.now(timezone.utc)
    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "logout",
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return make_response(message="Logged out successfully")


class RefreshTokenBody(BaseModel):
    """刷新令牌请求体（BUG-35：同时兼容 body 与 query 传参）"""

    refresh_token: Optional[str] = None


@router.post("/refresh", response_model=ApiResponse)
async def refresh_token(
    request: Request,
    body: Optional[RefreshTokenBody] = Body(None),
    refresh_token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    # 优先 body，兼容历史 query 传参（web-admin 现网实现使用 query）
    token_value = (body.refresh_token if body and body.refresh_token else None) or refresh_token
    if not token_value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="refresh_token is required (JSON body or query parameter)",
        )
    payload = decode_token(token_value)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    username = payload.get("sub")
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user or not user.is_active or _token_revoked(payload, user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    token_data = {
        "sub": user.username,
        "rv": user.token_revoked_at.isoformat() if user.token_revoked_at else None,
    }
    access_token = create_access_token(data=token_data)
    new_refresh_token = create_refresh_token(data=token_data)

    return make_response(
        data={
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        }
    )


@router.get("/me", response_model=ApiResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return make_response(data=UserResponse.model_validate(current_user).model_dump())


@router.put("/me/password", response_model=ApiResponse)
async def change_password(
    request: Request,
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(password_data.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect old password")

    current_user.hashed_password = get_password_hash(password_data.new_password)
    await db.commit()

    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "change_password",
        ip_address=request.client.host if request.client else None,
    )

    return make_response(message="Password changed successfully")


@router.post("/register", response_model=ApiResponse)
async def register(
    request: Request,
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already registered")

    if user_data.email:
        result = await db.execute(select(User).where(User.email == user_data.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Email already registered")

    # 安全：公开注册端点绝不信任客户端提供的 role / org_id。
    # 否则任何人都能自注册为 super_admin 或挂入他人组织（提权 + 跨组织越权）。
    # 提升角色、分配组织只能由管理员通过 /api/users 完成。
    user = User(
        username=user_data.username,
        email=user_data.email,
        phone=user_data.phone,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password),
        role=SELF_REGISTRATION_ROLE,
        org_id=None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await AuditService.log_action(
        db,
        str(user.id),
        user.username,
        "register",
        ip_address=request.client.host if request.client else None,
    )

    return make_response(
        data=UserResponse.model_validate(user).model_dump(),
        message="User registered successfully",
    )
