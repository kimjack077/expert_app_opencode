from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.utils.roles import is_admin, is_super_admin

# BUG-34：auto_error=False + 手动抛 401。FastAPI HTTPBearer 默认在
# 缺失 Authorization 头时抛 403，违背"未认证=401"的 HTTP 语义，
# 且会导致前端只识别 401 跳登录的拦截器失效。
security = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc), "type": "access"})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc), "type": "refresh"})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def _token_revoked(payload: dict, user: User) -> bool:
    """判断 token 的当前会话或旧版全局版本是否已被吊销。"""
    session_id = payload.get("sid")
    revoked_sessions = getattr(user, "revoked_sessions", None) or []
    if session_id and session_id in revoked_sessions:
        return True

    # Keep the timestamp check for legacy tokens issued before session IDs were
    # introduced. New tokens are revoked by session and do not affect peers.
    if session_id:
        return False

    revoked_at = getattr(user, "token_revoked_at", None)
    if revoked_at is None:
        return False
    # rv 是登录时看到的最近吊销版本。登出会更新该时间戳，使此前签发的
    # access/refresh token 全部失效；再次登录携带当前版本，可立即正常使用。
    return payload.get("rv") != revoked_at.isoformat()


async def get_user_from_token(token: str, db: AsyncSession) -> User:
    """Get user from a token string (used for export endpoints with query param auth)"""
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None or _token_revoked(payload, user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # 缺失 Authorization 头统一返回 401（而非 HTTPBearer 默认的 403）
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    if payload.get("type") != "access":
        raise credentials_exception

    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    if _token_revoked(payload, user):
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """可选鉴权：有合法 Bearer token 时返回用户，否则返回 ``None``。

    用于「优先 Header、回退 Query」的兼容场景（如报告导出），避免
    ``get_current_user`` 在无 Header 时直接抛 401 而阻断旧版 ``?token=`` 通道。
    """
    if credentials is None:
        return None
    token = credentials.credentials
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        return None
    username: str = payload.get("sub")
    if username is None:
        return None
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None or _token_revoked(payload, user) or not user.is_active:
        return None
    return user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    # 角色判断统一走 app/utils/roles.py —— 硬编码列表会让「谁是管理员」
    # 在不同端点漂移（项目里已发生过：超管在记录列表看不到全部数据）。
    if not is_admin(current_user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )
    return current_user


async def get_current_super_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if not is_super_admin(current_user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin permission required",
        )
    return current_user
