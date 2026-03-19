from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from contextlib import asynccontextmanager
import os
from datetime import datetime

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
from app.middleware import AuditMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    yield


app = FastAPI(
    title="专家现场工作辅助系统 API",
    description="Expert Field Inspection System API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
    redirect_slashes=False,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
app.include_router(statistics_router, prefix="/api/statistics", tags=["审核统计"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": str(exc),
            "data": None,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


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
    if full_path.startswith("h5/"):
        index_path = os.path.join(H5_APP_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
    index_path = os.path.join(WEB_ADMIN_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Page not found"}
