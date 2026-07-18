from datetime import datetime
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User
from app.services import AuditService
from app.utils.security import decode_token


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # 跳过流式响应的请求，避免阻塞
        if isinstance(response, StreamingResponse):
            return response

        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            try:
                # 从 JWT token 提取用户信息
                user_id = None
                username = None
                auth_header = request.headers.get("authorization")
                if auth_header and auth_header.lower().startswith("bearer "):
                    token = auth_header[7:].strip()
                    payload = decode_token(token)
                    if payload and payload.get("type") == "access":
                        username = payload.get("sub")

                async with AsyncSessionLocal() as db:
                    # 根据用户名查询 user_id
                    if username:
                        result = await db.execute(
                            select(User.id).where(User.username == username)
                        )
                        user_id = result.scalar_one_or_none()

                    await AuditService.log_action(
                        db=db,
                        user_id=user_id,
                        username=username,
                        action=f"{request.method} {request.url.path[:95]}",
                        resource_type="api",
                        resource_id=None,
                        detail={
                            "path": request.url.path,
                            "status_code": response.status_code,
                        },
                        ip_address=request.client.host if request.client else None,
                        user_agent=request.headers.get("user-agent"),
                    )
                    await db.commit()
            except Exception as e:
                print(f"AuditMiddleware error: {e}")

        return response
