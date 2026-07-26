import asyncio
import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User
from app.services import AuditService
from app.utils.security import decode_token

logger = logging.getLogger(__name__)

# 只审计成功的写操作。失败请求（401/403/422/5xx）不构成业务变更，
# 记录它们会让审计表被无效流量淹没，也拖慢热路径。
_AUDITED_METHODS = frozenset({"POST", "PUT", "DELETE", "PATCH"})


async def _write_audit_log(
    *,
    username: str | None,
    method: str,
    path: str,
    status_code: int,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    """在请求响应之后异步落审计日志，不占用请求延迟。"""
    try:
        async with AsyncSessionLocal() as db:
            user_id = None
            if username:
                result = await db.execute(
                    select(User.id).where(User.username == username)
                )
                user_id = result.scalar_one_or_none()

            await AuditService.log_action(
                db=db,
                user_id=user_id,
                username=username,
                action=f"{method} {path[:95]}",
                resource_type="api",
                resource_id=None,
                detail={"path": path, "status_code": status_code},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            await db.commit()
    except Exception:
        # 审计失败不能影响业务请求，但必须留下可检索的堆栈，
        # 否则审计缺口是完全不可见的。
        logger.exception("AuditMiddleware failed to write audit log")


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # 跳过流式响应的请求，避免阻塞
        if isinstance(response, StreamingResponse):
            return response

        if request.method not in _AUDITED_METHODS:
            return response
        if not (200 <= response.status_code < 300):
            return response

        username = None
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            payload = decode_token(auth_header[7:].strip())
            if payload and payload.get("type") == "access":
                username = payload.get("sub")

        # 后台执行：审计写入不再串行阻塞响应返回。
        asyncio.create_task(
            _write_audit_log(
                username=username,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
        )

        return response
