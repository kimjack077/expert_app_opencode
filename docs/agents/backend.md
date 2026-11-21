# 后端约定（FastAPI）

FastAPI + PostgreSQL + SQLAlchemy(async) + Alembic，Python 3.11+。入口 `backend/app/main.py`。

## 目录布局

```
backend/app/
├── config.py       # pydantic BaseSettings（不是 app/core/config.py）
│                   # DATABASE_URL(asyncpg) 与 DATABASE_URL_SYNC(alembic) 由此计算
├── main.py         # 应用装配、include_router、全局异常处理、SPA catch-all
├── models/         # SQLAlchemy ORM
├── schemas/        # Pydantic 请求/响应模型
├── routers/        # 全部路由（没有 app/api/ 包）
├── services/       # 业务逻辑
├── agents/         # Agent 共享运行时（详见 ai-agent.md）
├── middleware/     # audit_middleware.py
└── utils/          # security(JWT) / response / roles / soft_delete
                    # file_handler / storage_path / document_parser / llm_fallback
```

## 路由与前缀

API **不做版本化**，没有 `/api/v1/`。前缀在 `main.py` 的 `include_router()` 处指定，
唯二例外是 `audit_projects.py` 与 `project_agent.py`——它们在模块内自声明
`prefix="/api/audit-projects"`（所以 `main.py` 里对这两个只传 `tags`）。

| 模块 | 前缀 | 职责 |
|------|------|------|
| `auth.py` | `/api/auth` | JWT 登录、注册、刷新、当前用户 |
| `templates.py` | `/api/templates` | 检查模板与模板项 CRUD |
| `tasks.py` | `/api/tasks` | 检查任务分配、开始/完成、进度 |
| `records.py` | `/api/records` | 检查记录 CRUD、AI 建议写回 |
| `audit_projects.py` | `/api/audit-projects` | 审核项目、工作组、计划项、区域记录、不符合项、报告导出 |
| `project_agent.py` | `/api/audit-projects` | 项目级 Agent：文档、会话、证据、草稿、成果 |
| `agent.py` | `/api/agent` | 对话 Agent、动作确认、规划器、通知、反馈统计 |
| `knowledge.py` | `/api/knowledge` | 知识库分类/文档、RAG 索引 |
| `llm.py` | `/api/llm` | 建议 / 依据 / 最终判定（含流式） |
| `ai_extract.py` | `/api/ai-extract` | 从 PDF/Word/Excel 提取模板 |
| `ai_enhanced.py` | `/api/ai-enhanced` | 多模态增强（照片分析等） |
| `enterprises.py` | `/api/enterprises` | 企业、资质、产品、设备、人员 |
| `industries.py` | `/api/industries` | 行业分类字典 |
| `users.py` | `/api/users` | 用户与角色 |
| `media.py` | `/api/media` | 文件上传与管理 |
| `analytics.py` | `/api/analytics` | 仪表盘统计、审计日志 |
| `statistics.py` | `/api/statistics` | 审核统计报表 |

交互文档 `/api/docs`，ReDoc `/api/redoc`，健康检查 `/api/health`。

## 服务层

```
services/
├── llm_service.py               # LLM 调用封装（建议/依据/最终判定 + 流式）
├── rag_service.py               # 知识向量检索
├── agent_service.py             # 对话 Agent：有界多轮工具循环 + SSE
├── agent_actions.py             # 动作注册表（写回一律走确认卡）
├── agent_memory_service.py      # 长期记忆（AgentMemory）
├── agent_feedback_service.py    # 采纳率/反馈闭环统计
├── agent_proactive_service.py   # 主动巡检 → AgentNotification
├── audit_agent.py               # 审核准备、证据评估、报告叙述、NC 建议
├── evidence_agent_service.py    # 证据收集管线
├── multimodal_service.py        # 视觉/多模态照片分析
├── ai_extract_service.py        # 文档解析 → 模板抽取
├── project_knowledge_service.py / project_document_parser.py
├── project_artifact_service.py  # 项目成果（报告包）生成
├── report_generator.py / report_service.py   # Word/PDF 报告
├── template_recommendation_service.py
├── project_access_service.py    # 项目级访问控制
└── formal_audit_sync_service.py # 任务流 ↔ 正式审核流 的胶水（无 AI）
```

## 横切约定

**统一响应体**：所有端点返回 `{code, message, data, timestamp}`。
从 `app/utils/response.py` 引入 `make_response` / `utc_now_iso`。
⚠️ 历史遗留：仍有 15 个路由各自定义了本地 `make_response`（只有 3 个已改为引入统一实现）。
改动路由时顺手换成统一引入，不要再新增本地副本。

**角色判断**：统一引用 `app/utils/roles.py`（`ADMIN_ROLES`、`RECORD_VIEW_ALL_ROLES`、
`is_admin()`、`can_view_all_records()`），不要在路由里硬编码 `role != "admin"`。
角色语义见 [data-model.md](data-model.md)。

**鉴权**：`access_token` 8h + `refresh_token` 30d；请求头 `Authorization: Bearer <token>`。
依赖注入用 `Depends(get_current_user)` / `Depends(get_current_admin_user)`。
- **缺失/无效凭证统一返回 401**（不是 403），前端靠 401 触发刷新/跳登录。
- `POST /api/auth/refresh` 同时接受 **JSON body**（`{"refresh_token": "..."}`）与
  **query 参数**（历史兼容，web-admin 在用），两者都缺返回 422。

**任务更新权限**：`PUT /api/tasks/{id}` 对 expert 只允许改 `status` 与 `remarks`
（remarks 是 H5 提交流程写入"最终判定"的唯一通道，其他字段仍仅管理员可改）。

**审核项目写接口的 project_id**：`POST /{project_id}/meetings` 与
`/{project_id}/report` 的 body `project_id` 为**可选**，以路径参数为准；
传了但与路径不一致返回 422。

**软删除**：业务实体用 `SoftDeleteMixin`（`is_deleted` + `deleted_at`），
工具函数在 `app/utils/soft_delete.py`。所有查询必须过滤 `is_deleted == False`。
带唯一约束的字段（`code`、`project_no` 等）软删除时追加 `_deleted_<timestamp>` 后缀。
`audit_logs` 永不软删除。

**审计日志**：写操作由 `middleware/audit_middleware.py` 自动落 `AuditLog`；
需要手工补记时用 `AuditService.log_action()`。

**全局异常处理**（`main.py`）按**异常消息字符串匹配**归类：
非法 UUID → 404，外键/唯一约束冲突 → 409，其余 → 500。
⚠️ 修改异常文案前先确认不会打乱这个映射。

**文件上传**：UUID 文件名 + MIME 校验，落 `backend/uploads/`，静态挂载在 `/uploads`。
路径拼接走 `utils/storage_path.py`，读写走 `utils/file_handler.py`。

## 代码风格：Python

导入分三组，组间空行，组内按字母序：标准库 → 第三方 → `from app.*`。

```python
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.utils.response import make_response
```

- 命名：函数/变量 `snake_case`，类 `PascalCase`，常量 `UPPER_SNAKE_CASE`。
- 路由声明：`router = APIRouter(prefix="/api/xxx", tags=["xxx"])`。
- Schema 命名：`*Base` / `*Create` / `*Update` / `*Response`，继承 `BaseModel`，
  校验用 `Field(...)`，响应模型加 `class Config: from_attributes = True`。
- 数据库**全异步**：`AsyncSession`、`await db.execute()`、预加载用 `selectinload`、
  会话注入用 `Depends(get_db)`、取单条用 `result.scalar_one_or_none()`。
- 错误抛 `HTTPException(status_code=..., detail=...)`。
