# AGENTS.md

Guidelines for agentic coding agents working in this repository.

## Project Overview

专家现场工作辅助系统 (Expert Field Inspection System - EFIS) - 一个完整的认证审核现场工作辅助系统，包含三大核心组件：

- **Backend**: FastAPI (Python 3.11+) + PostgreSQL + SQLAlchemy (async) + Alembic
- **Web Admin**: React 18 + TypeScript + Ant Design + Vite
- **H5 Mobile App**: Vue 3 + Vant UI + Vite

**关键业务能力**：
- 审核项目全生命周期管理
- AI Agent 辅助审核（RAG + LLM）
- 检查模板设计与复用
- 现场检查记录与数据采集
- 审核报告自动生成
- 知识库与智能问答

## Build/Lint/Test Commands

### Backend (FastAPI)

```bash
cd backend
.venv\Scripts\activate                    # Windows: activate venv
pip install -r requirements.txt           # Install dependencies
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000  # Dev server
alembic upgrade head                      # Run migrations (仅本地运行一次)
alembic revision --autogenerate -m "description"  # Create migration
python -m pytest tests/ -v                # Run all tests
python -m pytest tests/test_file.py -v    # Run single test file
python test_all_crud.py                   # Run comprehensive CRUD tests
```

### Web Admin (React)

```bash
cd web-admin
npm install
npm run dev                               # Dev server (uses .env.development)
npm run build                             # Production build (tsc && vite build)
npx tsc --noEmit                          # Type check only
```

### H5 App (Vue 3)

```bash
cd h5-app
npm install
npm run dev                               # Dev server
npm run build                             # Production build (includes type-check)
npm run type-check                        # vue-tsc --build
npm run format                            # oxfmt src/ (no semicolons, single quotes)
```

**Node requirement**: `^20.19.0 || >=22.12.0`

## Core Modules & Routes

### Backend API Modules

| Module | Router | Prefix | Description |
|--------|--------|--------|-------------|
| Auth | auth.py | `/api/auth` | JWT 登录、注册、令牌刷新 |
| Templates | templates.py | `/api/templates` | 检查模板 CRUD、项目管理、AI 辅助录入 |
| Tasks | tasks.py | `/api/tasks` | 检查任务分配、进度跟踪 |
| Records | records.py | `/api/records` | 检查记录 CRUD、项目详情、AI 建议 |
| Audit Projects | audit_projects.py | `/api/audit-projects` | 审核项目、工作组、计划项、区域记录、不符合项 |
| AI Agent | agent.py | `/api/agent` | AI 助手对话、检查建议 |
| Project Agent | project_agent.py | `/api/agent/projects` | 项目级 AI 审核、文档管理、成果生成 |
| Knowledge | knowledge.py | `/api/knowledge` | 知识库分类、文档管理、RAG 索引 |
| Users | users.py | `/api/users` | 用户管理、角色权限 |
| Enterprises | enterprises.py | `/api/enterprises` | 企业管理、资质信息 |
| Industries | industries.py | `/api/industries` | 行业分类字典 |
| Media | media.py | `/api/media` | 文件上传、图片管理 |
| LLM | llm.py | `/api/llm` | LLM 建议生成 |
| AI Extract | ai_extract.py | `/api/ai-extract` | AI 辅助数据提取 |
| AI Enhanced | ai_enhanced.py | `/api/ai-enhanced` | AI 增强功能（多模态等） |
| Analytics | analytics.py | `/api/analytics` | 数据分析统计 |
| Statistics | statistics.py | `/api/statistics` | 审核统计报表 |

### Core Services

```
services/
├── agent_service.py          # AI 助手服务
├── audit_agent.py            # 审核 Agent 核心逻辑
├── evidence_agent_service.py # 证据收集 Agent
├── llm_service.py            # LLM 调用封装
├── multimodal_service.py     # 多模态 AI 服务
├── rag_service.py            # RAG 知识库检索
├── report_generator.py       # 审核报告生成
├── report_service.py         # 报告业务逻辑
├── project_knowledge_service.py  # 项目知识库服务
├── project_artifact_service.py   # 项目成果管理
├── project_document_parser.py    # 文档解析
├── ai_extract_service.py     # AI 提取服务
├── template_recommendation_service.py  # 模板推荐
└── project_access_service.py # 项目访问权限控制
```

## Key Architecture Patterns

### Auth
- JWT `access_token` (8h) + `refresh_token` (30d)
- `Depends(get_current_user)` / `Depends(get_current_admin_user)` 权限检查
- 前端发送 `Authorization: Bearer <token>`

### Soft Delete (软删除)
- 所有业务实体使用软删除模式（标记 `is_deleted=True`，保留数据）
- 使用 `SoftDeleteMixin` 统一添加 `is_deleted` 和 `deleted_at` 字段
- 所有查询自动过滤 `is_deleted == False` 的记录
- 唯一字段软删除时追加 `_deleted_<timestamp>` 后缀避免约束冲突
- 工具函数：`app/utils/soft_delete.py`

### Audit
- 所有写操作自动记录审计日志（`AuditMiddleware`）
- 使用 `AuditService.log_action()` 手动记录

### File Uploads
- UUID 文件名，MIME 类型验证
- 存储路径：`uploads/`
- 文件管理：`utils/file_handler.py`

### RAG (Retrieval-Augmented Generation)
- 知识库文档向量化存储
- 检索增强生成，提供上下文相关的 AI 建议
- `rag_service.py` 封装 RAG 核心逻辑

### Path Aliases
- Frontend: `@/` → `src/`
- Backend: `app.*` → `app/`

## Code Style: Python (Backend)

**Imports** - Group in order, each group separated by blank line:
1. Standard library (alphabetically)
2. Third-party (alphabetically)
3. Local imports (`from app.*`)

```python
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
```

**Naming**: `snake_case` functions/vars, `PascalCase` classes, `UPPER_SNAKE_CASE` constants.
**Routers**: `router = APIRouter(prefix="/api/xxx", tags=["xxx"])`.
**Schemas**: `*Base`, `*Create`, `*Update`, `*Response` naming; inherit from `BaseModel`; use `Field(...)` for validation; add `class Config: from_attributes = True` for response models.
**Database**: Always async - `AsyncSession`, `await db.execute()`, `selectinload` for eager loading, `Depends(get_db)` for injection.
**Error handling**: `HTTPException(status_code=..., detail=...)`, always check auth with `Depends(get_current_user)`, use `result.scalar_one_or_none()` for single results.
**Response format**: All endpoints return `{code, message, data, timestamp}` via `make_response()`.

## Code Style: TypeScript/React (Web Admin)

**Imports** - Use `@/` alias for src, group by: React → libraries → local.
```typescript
import { useState, useEffect } from 'react'
import { Card, Table, Button } from 'antd'
import { taskApi } from '@/services/api'
```

**Naming**: PascalCase components (export default), camelCase vars/functions, PascalCase types.
**Components**: Functional with hooks, `const [s, setS] = useState<Type>()`, destructure props.
**State**: Zustand stores in `stores/`, API calls in `services/api.ts` and `services/auditProjectApi.ts`.
**Ant Design**: Use `Form` + `form.submit()`, `message.success()`/`message.error()` for notifications.

## Code Style: Vue 3 (H5 App)

```vue
<script setup>
import { ref, onMounted } from 'vue'
const items = ref([])
const loading = ref(false)
</script>
```

**Formatting**: oxfmt - no semicolons, single quotes. **Naming**: camelCase vars, PascalCase component files.
**Vant**: Use `van-` prefix components, `van-pull-refresh` + `van-list` for infinite scroll.
**CSS**: Scoped styles, CSS variables (`--primary-color`, `--bg-white`).

## Database Structure

### Core Tables

```
├── users                    # 用户表（软删除）
├── organizations            # 组织机构表（软删除）
├── enterprises              # 企业表（软删除）
├── enterprise_qualifications # 企业资质（软删除）
├── industries               # 行业分类（软删除）
├── inspection_templates     # 检查模板（软删除）
├── template_items           # 模板项目（软删除，层级结构）
├── inspection_tasks         # 检查任务（软删除）
├── inspection_records       # 检查记录（软删除）
├── audit_projects           # 审核项目（软删除，核心业务实体）
├── audit_team_members       # 审核组成员（软删除）
├── audit_plan_items         # 审核计划项（软删除）
├── audit_areas              # 审核区域
├── audit_area_records       # 审核区域记录
├── nonconformities          # 不符合项
├── audit_reports            # 审核报告
├── knowledge_categories     # 知识分类（软删除）
├── knowledge_documents      # 知识文档（软删除）
├── media_files              # 媒体文件（软删除）
├── project_artifacts        # 项目成果（软删除）
├── project_documents        # 项目文档（软删除）
├── rag_documents            # RAG 文档索引
├── agent_conversations      # Agent 对话记录
├── evidence_agent_sessions  # 证据收集会话
└── audit_logs               # 审计日志（不可软删除）
```

### Database Migrations

本地开发和远程服务器使用 **同一个远程 PostgreSQL 数据库** (`PG_HOST=49.232.213.79`)，因此：

- **迁移只需要在本地运行一次**，远程服务器共享同一个数据库，无需再次迁移
- 模型变更后：`cd backend && alembic revision --autogenerate -m "description" && alembic upgrade head`
- **部署时不需要执行迁移**，数据库已同步

## Environment Config

### Backend

```env
PG_HOST=49.232.213.79           # 远程数据库地址（本地和服务器共享）
PG_PORT=5432
PG_DB=db_expert_claude
PG_USER=ad_admin_claude
PG_PASSWORD=***

SECRET_KEY=efis-secret-key-change-in-production-2024
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
REFRESH_TOKEN_EXPIRE_DAYS=30

# LLM Configuration
LLM_BASE_URL=https://token.sensenova.cn/v1
LLM_MODEL=deepseek-v4-flash
LLM_API_KEY=***

# RAG/Embedding
EMBEDDING_BASE_URL=https://api.edgefn.net/v1
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_API_KEY=***

UPLOAD_DIR=./uploads
MAX_FILE_SIZE=10485760
DEBUG=true
```

### Frontend

- `web-admin/.env.development` / `.env.production` - `VITE_API_URL`
- `h5-app/.env.development` / `.env.production` - `VITE_API_URL`

## User Roles

| Role | Permissions |
|------|-------------|
| `super_admin` | 完全访问权限 |
| `admin` | 模板/任务/企业管理 |
| `expert` | 执行检查、提交记录 |
| `auditor` | 只读访问 |

## Deployment

本地和远程服务器共享同一个数据库，部署流程：

1. 本地运行迁移（仅首次或模型变更后）：`alembic upgrade head`
2. 提交代码到 GitHub
3. 运行部署脚本：`python deploy.py`（部署脚本已跳过迁移步骤）
4. 验证服务状态：http://49.232.213.79

**服务地址**：
- 后端 API: http://49.232.213.79:8000
- Web Admin: http://49.232.213.79:3000
- H5 App: http://49.232.213.79:5173

**关键要点**：由于数据库共享，本地测试会影响远程服务器数据，测试完成后建议清理测试数据。

## Project Structure

```
backend/app/
├── models/          # SQLAlchemy ORM models (17个业务模型)
├── schemas/         # Pydantic request/response models
├── routers/         # FastAPI route handlers (16个路由模块)
├── services/        # Business logic (14个服务模块)
├── utils/           # Security (JWT), file handling, soft_delete
└── middleware/      # AuditMiddleware

web-admin/src/
├── pages/           # Route-based page components
│   ├── AuditProjects/   # 审核项目管理（核心页面）
│   ├── Templates/       # 模板管理
│   ├── Records/         # 检查记录
│   ├── Tasks/           # 检查任务
│   ├── Knowledge/       # 知识库
│   ├── Enterprises/     # 企业管理
│   ├── Users/           # 用户管理
│   └── Analytics/       # 数据分析
├── components/      # Shared components (MainLayout, AgentSidebar)
├── stores/          # Zustand state (auth, app)
└── services/        # API client (api.ts, auditProjectApi.ts)

h5-app/src/
├── views/           # Vue page components
│   ├── AiAuditSession.vue   # AI 审核会话
│   ├── InspectionExecution.vue # 检查执行
│   ├── AuditTasks.vue       # 审核任务
│   └── Records.vue          # 检查记录
├── api/             # API modules
├── components/      # AgentChat, AiAssistCard 等组件
├── utils/           # photoUtils
└── main.js          # Entry with Vant registration
```

## Testing

### Automated Tests
- `tests/` - 单元测试（agent_service, llm_service, rag_service, project_audit_agent）
- `test_all_crud.py` - 综合 CRUD 测试（覆盖所有核心模块）

### Manual Testing
- Web Admin: http://localhost:3000
- H5 App: http://localhost:5173
- API Docs: http://localhost:8000/api/docs

## Important Notes

1. **数据库共享**：本地和服务器使用同一数据库，迁移只在本地执行
2. **软删除**：所有业务实体使用软删除，查询需过滤 `is_deleted == False`
3. **唯一字段处理**：软删除时唯一字段（如 `code`, `project_no`）需追加后缀避免冲突
4. **RAG 索引**：知识库文档上传后自动生成向量索引，需 LLM API 配置正确
5. **文件存储**：上传文件存储在 `backend/uploads/`，部署时需同步
6. **前端代理**：开发环境前端通过 Vite proxy 访问后端 API
