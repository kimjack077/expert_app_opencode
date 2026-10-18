from datetime import datetime, timedelta, timezone
from typing import Optional
import time
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


# ---------------------------------------------------------------------------
# bcrypt 的异步包装（PERF）
#
# bcrypt 是纯 CPU 密集操作，单次 checkpw 在线上 4 核小机上约 250~300ms。
# 直接在 async 路由里调用会**阻塞整个事件循环**：10 个并发登录实测被串成
# 2.9 秒（p50 2925ms），期间所有其他请求（包括检查项保存）一起卡住。
# 登录/改密属于低频操作，但恰恰容易在演示现场多人同时登录时集中触发。
#
# 因此异步路由一律使用下面两个包装：把 bcrypt 丢到线程池，事件循环继续服务
# 其他请求。同步版本保留给脚本/测试与线程内调用。
# ---------------------------------------------------------------------------
async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(verify_password, plain_password, hashed_password)


async def get_password_hash_async(password: str) -> str:
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(get_password_hash, password)


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


# ---------------------------------------------------------------------------
# 鉴权用户短 TTL 进程内缓存（PERF）
#
# 原实现里每个受保护请求都要执行一次 ``SELECT ... FROM users``（鉴权链路的
# 第一个查询）。本地开发连公网远程库时，这一次查询就是一次 50~800ms 的网络
# 往返，是所有页面"转一圈才出来"的主要来源之一。
#
# 这里按 username 缓存用户**列值快照**（TTL 默认 60s，可用
# ``AUTH_USER_CACHE_TTL_SECONDS=0`` 关闭），命中时构造一个**全新的瞬态**
# ``User`` 实例返回——每次新建而不是共享同一实例，避免瞬态对象被并发请求
# 意外挂进各自的 Session。
#
# 一致性约定（务必遵守）：
# * 任何**写** user 表的地方（登出吊销会话、改密、管理员改角色/停用、删除），
#   必须在 commit 后调用 :func:`invalidate_user_cache`。当前已接入：
#   auth.logout / auth.change_password / users.update_user / users.delete_user。
# * 直接改库或跨进程写入不会被感知，最长 TTL 秒后生效。
# * 命中缓存返回的是瞬态对象：只允许**读**列属性；需要修改当前用户时必须
#   ``await db.get(User, current_user.id)`` 重新取托管实例（auth.py 已示范）。
# ---------------------------------------------------------------------------
_USER_CACHE_MAX = 500
# username -> (monotonic 过期时刻, 列值快照)
_user_cache: dict[str, tuple[float, dict]] = {}


def invalidate_user_cache(username: Optional[str] = None) -> None:
    """使用户缓存失效。``username=None`` 时清空全部（用户表批量变更时用）。"""
    if username is None:
        _user_cache.clear()
    else:
        _user_cache.pop(username, None)


def _snapshot_user(user: User) -> dict:
    """提取全部列值为普通 dict，供缓存与瞬态实例重建。"""
    return {c.name: getattr(user, c.name) for c in User.__table__.columns}


async def _load_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """按用户名加载用户，优先命中进程内短 TTL 缓存。

    缓存未命中时走数据库，返回的是 Session 托管实例（与历史行为一致）；
    命中时返回瞬态实例（只读列属性安全）。未找到用户不做负缓存。
    """
    ttl = settings.AUTH_USER_CACHE_TTL_SECONDS
    if ttl > 0:
        hit = _user_cache.get(username)
        if hit is not None:
            expires_at, snapshot = hit
            if time.monotonic() < expires_at:
                return User(**snapshot)
            _user_cache.pop(username, None)

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        return None

    if ttl > 0:
        if len(_user_cache) >= _USER_CACHE_MAX:
            # 规模兜底：直接清空重建。500 个活跃用户远超本系统实际规模，
            # 真触发了也只是回到"每请求查库"，不会出错。
            _user_cache.clear()
        _user_cache[username] = (
            time.monotonic() + ttl,
            _snapshot_user(user),
        )
    return user


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

    user = await _load_user_by_username(db, username)
    if user is None or user.is_deleted or _token_revoked(payload, user):
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

    user = await _load_user_by_username(db, username)
    if user is None or user.is_deleted:
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
    user = await _load_user_by_username(db, username)
    if user is None or user.is_deleted or _token_revoked(payload, user) or not user.is_active:
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
