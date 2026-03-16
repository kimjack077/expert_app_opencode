from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
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
    get_current_user,
)
from app.services import AuditService

router = APIRouter()


def make_response(data=None, code=200, message="success"):
    return ApiResponse(
        code=code, message=message, data=data, timestamp=datetime.utcnow()
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

    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})

    user.last_login_at = datetime.utcnow()
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
    await AuditService.log_action(
        db,
        str(current_user.id),
        current_user.username,
        "logout",
        ip_address=request.client.host if request.client else None,
    )
    return make_response(message="Logged out successfully")


@router.post("/refresh", response_model=ApiResponse)
async def refresh_token(
    request: Request, refresh_token: str, db: AsyncSession = Depends(get_db)
):
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    username = payload.get("sub")
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    access_token = create_access_token(data={"sub": user.username})
    new_refresh_token = create_refresh_token(data={"sub": user.username})

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
        raise HTTPException(status_code=400, detail="Username already registered")

    if user_data.email:
        result = await db.execute(select(User).where(User.email == user_data.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        username=user_data.username,
        email=user_data.email,
        phone=user_data.phone,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password),
        role=user_data.role,
        org_id=user_data.org_id,
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
