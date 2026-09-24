from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from contextlib import asynccontextmanager
import os
from datetime import datetime, timezone

from sqlalchemy.exc import DBAPIError

from app.config import settings
from app.routers import (
    auth_router,
    templates_router,
    tasks_router,
    records_router,
    media_router,
    llm_router,
    analytics_router,
    enterprises_router,
    knowledge_router,
    ai_extract_router,
    industries_router,
    users_router,
    agent_router,
    ai_enhanced_router,
    statistics_router,
)
from app.routers.audit_projects import router as audit_projects_router
from app.routers.project_agent import router as project_agent_router
from app.middleware import AuditMiddleware


async def recover_stale_artifact_jobs() -> None:
    """将上次进程退出时残留的成果生成任务标记为失败。

    成果生成走 FastAPI ``BackgroundTasks``，进程重启不会恢复执行，
    残留任务会永远停在 ``generating``，用户既看不到结果也无法重试。
    启动时统一回收，让前端能重新提交。
    """
    from sqlalchemy import update

    from app.database import AsyncSessionLocal
    from app.models.project_artifact import ProjectArtifact

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                update(ProjectArtifact)
                .where(ProjectArtifact.status == "generating")
                .values(
                    status="failed",
                    error_message="服务重启导致任务中断，请重新生成",
                )
            )
            await db.commit()
            if result.rowcount:
                print(f"[startup] 回收中断的成果生成任务: {result.rowcount} 个")
    except Exception as exc:  # 启动阶段不因回收失败而阻断服务
        print(f"[startup] 回收成果生成任务失败: {exc}")


async def _proactive_scan_loop():
    """后台主动巡检循环（#6）。

    每 PROACTIVE_SCAN_INTERVAL_SECONDS 扫描一次，生成主动提醒。
    通知落库，因此进程重启不会丢失历史提醒；循环本身重启后自然重新开始。
    """
    import asyncio

    from app.database import AsyncSessionLocal
    from app.services.agent_proactive_service import agent_proactive_service

    interval = settings.PROACTIVE_SCAN_INTERVAL_SECONDS
    if interval <= 0:
        return
    while True:
        try:
            async with AsyncSessionLocal() as db:
                await agent_proactive_service.scan(db)
        except Exception as exc:
            print(f"[Proactive] scan failed: {type(exc).__name__}: {exc}")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    await recover_stale_artifact_jobs()
    scan_task = None
    if settings.PROACTIVE_SCAN_INTERVAL_SECONDS > 0:
        scan_task = asyncio.create_task(_proactive_scan_loop())
    try:
        yield
    finally:
        if scan_task:
            scan_task.cancel()


app = FastAPI(
    title="易审通 (EasyAudit) API",
    description="易审通 (EasyAudit) 认证审核与现场评审智能云平台 API",
    version="2.4.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
    redirect_slashes=True,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGIN_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AuditMiddleware)

if os.path.exists(settings.UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

app.include_router(auth_router, prefix="/api/auth", tags=["认证"])
app.include_router(templates_router, prefix="/api/templates", tags=["检查模板"])
app.include_router(records_router, prefix="/api/records", tags=["检查记录"])
app.include_router(tasks_router, prefix="/api/tasks", tags=["检查任务"])
app.include_router(media_router, prefix="/api/media", tags=["文件上传"])
app.include_router(llm_router, prefix="/api/llm", tags=["LLM建议"])
app.include_router(analytics_router, prefix="/api/analytics", tags=["数据分析"])
app.include_router(enterprises_router, prefix="/api/enterprises", tags=["企业管理"])
app.include_router(knowledge_router, prefix="/api/knowledge", tags=["知识库"])
app.include_router(ai_extract_router, prefix="/api/ai-extract", tags=["AI辅助录入"])
app.include_router(industries_router, prefix="/api/industries", tags=["行业分类"])
app.include_router(users_router, prefix="/api/users", tags=["用户管理"])
app.include_router(agent_router, prefix="/api/agent", tags=["AI助手"])
app.include_router(ai_enhanced_router, prefix="/api/ai-enhanced", tags=["AI增强功能"])
app.include_router(audit_projects_router, tags=["审核项目"])
app.include_router(project_agent_router, tags=["项目审核 Agent"])
app.include_router(statistics_router, prefix="/api/statistics", tags=["审核统计"])


def _error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": status_code,
            "message": message,
            "data": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


# PostgreSQL SQLSTATE → HTTP 状态码。
# 依据错误码判断，而不是匹配驱动的英文错误文案：
# 文案会随驱动版本、数据库 locale 变化，字符串匹配随时失效。
_SQLSTATE_STATUS = {
    "23503": (409, "数据冲突，可能存在关联引用"),  # foreign_key_violation
    "23505": (409, "数据冲突，该记录已存在"),      # unique_violation
    "23502": (400, "缺少必填字段"),                # not_null_violation
    "22P02": (404, "资源不存在"),                  # invalid_text_representation(非法 UUID 等)
    "22000": (404, "资源不存在"),                  # data_exception(asyncpg 对非法 UUID 字面量抛 DataError)
    "22001": (400, "字段内容超长"),                # string_data_right_truncation(超长字段兜底)
}


@app.exception_handler(DBAPIError)
async def database_exception_handler(request: Request, exc: DBAPIError):
    sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None) or getattr(
        getattr(exc, "orig", None), "pgcode", None
    )
    mapped = _SQLSTATE_STATUS.get(sqlstate)
    if mapped:
        return _error_response(*mapped)

    print(f"[API] Database error [{sqlstate}]: {type(exc).__name__}: {exc}")
    return _error_response(500, "服务器暂时无法处理该请求，请稍后重试")


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    # 非法 UUID 字符串在进入数据库前就会抛 ValueError
    if "uuid" in str(exc).lower():
        return _error_response(404, "资源不存在")
    print(f"[API] ValueError: {exc}")
    return _error_response(500, "服务器暂时无法处理该请求，请稍后重试")


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request: Request, exc: RequestValidationError):
    """路径中的非法 UUID 统一按资源不存在处理，其余校验仍保持 FastAPI 422。"""
    invalid_path_uuid = any(
        error.get("type") in {"uuid_parsing", "uuid_type"}
        and tuple(error.get("loc", ()))[:1] == ("path",)
        for error in exc.errors()
    )
    if invalid_path_uuid:
        return _error_response(404, "资源不存在")
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"[API] Unhandled error: {type(exc).__name__}: {exc}")
    return _error_response(500, "服务器暂时无法处理该请求，请稍后重试")



@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


WEB_ADMIN_DIR = "/opt/efis/web-admin"
H5_APP_DIR = "/opt/efis/h5-app"

if os.path.exists(os.path.join(WEB_ADMIN_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(WEB_ADMIN_DIR, "assets")), name="web-admin-assets")

if os.path.exists(os.path.join(H5_APP_DIR, "assets")):
    app.mount("/h5/assets", StaticFiles(directory=os.path.join(H5_APP_DIR, "assets")), name="h5-assets")


@app.get("/")
async def serve_web_admin():
    index_path = os.path.join(WEB_ADMIN_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Web Admin not found"}


@app.get("/h5")
@app.get("/h5/")
async def serve_h5_app():
    index_path = os.path.join(H5_APP_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "H5 App not found"}


@app.get("/{full_path:path}")
async def serve_spa_routes(full_path: str):
    # API 路径未匹配到路由时返回标准 404 JSON，而不是 SPA index.html
    if full_path.startswith("api/") or full_path == "api":
        return JSONResponse(
            status_code=404,
            content={
                "code": 404,
                "message": "API endpoint not found",
                "data": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    if full_path.startswith("h5/"):
        index_path = os.path.join(H5_APP_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
    index_path = os.path.join(WEB_ADMIN_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Page not found"}
