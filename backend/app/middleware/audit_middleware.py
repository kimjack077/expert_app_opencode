from datetime import datetime
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.services import AuditService


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # 跳过流式响应的请求，避免阻塞
        if isinstance(response, StreamingResponse):
            return response

        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            try:
                async with AsyncSessionLocal() as db:
                    await AuditService.log_action(
                        db=db,
                        user_id=None,
                        username=None,
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
