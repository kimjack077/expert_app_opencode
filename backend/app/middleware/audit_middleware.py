import asyncio
import logging

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


class AuditMiddleware:
    """写操作审计中间件（**纯 ASGI**，不要改回 BaseHTTPMiddleware）。

    历史故障：本中间件曾继承 ``BaseHTTPMiddleware``。该基类会在响应体消费完毕后
    取消内部任务——对 SSE 流式端点是致命的：流收尾阶段（generator 的 finally）
    里的任何 await 都会被取消，请求级 DB session 进入 PendingRollbackError。
    真实后果是 Agent 的动作提案永远写不进 ``agent_messages``，
    导致 ``/api/agent/actions/confirm`` 一律 404。

    纯 ASGI 实现不包装/取消内部任务，流式响应（对话、简报、规划器、AI 判定流）
    得以正常收尾。
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        if method not in _AUDITED_METHODS:
            await self.app(scope, receive, send)
            return

        status_code: int | None = None

        async def send_wrapper(message):
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = message.get("status")
            await send(message)

        await self.app(scope, receive, send_wrapper)

        if status_code is None or not (200 <= status_code < 300):
            return

        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers") or []
        }
        username = None
        auth_header = headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            payload = decode_token(auth_header[7:].strip())
            if payload and payload.get("type") == "access":
                username = payload.get("sub")

        client = scope.get("client")
        # 后台执行：审计写入不串行阻塞响应返回。
        asyncio.create_task(
            _write_audit_log(
                username=username,
                method=method,
                path=scope.get("path", ""),
                status_code=status_code,
                ip_address=client[0] if client else None,
                user_agent=headers.get("user-agent"),
            )
        )
