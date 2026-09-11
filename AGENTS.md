# AGENTS.md

易审通 (EasyAudit) —— 面向认证机构、审核员与评审专家的认证审核 / 现场评审云平台。
本文件是给编码 Agent 的**入口索引**：只放硬约束和导航，细节在专题文档里按需读取。

## 硬约束（先读这三条）

> [!IMPORTANT]
> **1. 严禁自动部署。** 除非用户在当前对话中单独、明确地说"部署到服务器 / 运行 deploy"，
> 否则任何改动后**绝不**执行 `python deploy.py` 或任何部署脚本。
>
> **2. 严禁自动 push。** 除非用户单独、明确地说"推送到 GitHub / git push"，
> 否则**绝不**执行 `git push`。改完代码只做本地构建与测试校验，然后在对话里汇报。
>
> **3. 本地和线上共用同一个远程数据库**（`PG_HOST=49.232.213.79`，`PG_DB=db_expert_claude`）。
> 后果：迁移只在本地跑一次，部署不再迁移；本地冒烟测试会写脏生产数据，
> 跑完用 `scripts/clear_db_records.py` 清理。

## 技术栈与目录

| 目录 | 栈 | 端口 |
|------|-----|------|
| `backend/` | FastAPI + PostgreSQL + SQLAlchemy(async) + Alembic，Python 3.11+ | 8000 |
| `web-admin/` | React 18 + TS + Ant Design + Vite | 3000 |
| `h5-app/` | Vue 3 + Vant + Vite（base path `/h5/`） | 5174 |
| `mobile-app/` | React 18 + antd-mobile（早期端，Agent 写回已禁用） | 3001 |
| `inspection_app/` | Flutter 3.x + Riverpod + Dio + GoRouter（在建） | — |

核心业务能力：审核项目全生命周期 · AI Agent 辅助审核（RAG + LLM）·
检查模板设计与复用 · 现场检查记录采集 · 审核报告自动生成 · 知识库智能问答。

## 常用命令

```bash
# 后端（pytest 只装在 venv 里）
cd backend && .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
python -m pytest tests/ -v
alembic revision --autogenerate -m "描述" && alembic upgrade head   # 仅本地跑一次

# 管理后台
cd web-admin && npm install && npm run dev        # npm run build / npx tsc --noEmit

# H5（Node ^20.19.0 || >=22.12.0）
cd h5-app && npm install && npm run dev           # npm run build / type-check / format
```

## 专题文档（按需读，不要一次全读）

| 文档 | 什么时候读 |
|------|-----------|
| [docs/agents/backend.md](docs/agents/backend.md) | 改后端。路由前缀表、服务层地图、统一响应体 / 角色 / 软删除 / 审计 / 异常处理约定、Python 代码风格 |
| [docs/agents/frontend.md](docs/agents/frontend.md) | 改前端。三端目录结构、代理与别名、React/Vue 风格规则、离线能力的真实状态 |
| [docs/agents/data-model.md](docs/agents/data-model.md) | 碰数据库或业务流程。42 张表分域清单、哪些表是软删除、关键关系、**三套并行记录模型的架构债**、角色权限、迁移流程 |
| [docs/agents/ai-agent.md](docs/agents/ai-agent.md) | 碰 LLM / RAG / Agent。共享运行时 `app/agents/`、工具循环与人在回路、证据管线、Agent 端点清单、已知缺口 |
| [docs/agents/ops.md](docs/agents/ops.md) | 配环境、跑测试、部署。全部环境变量、两类测试文件的区别、部署脚本与线上拓扑 |

`CLAUDE.md` 与本文件内容重叠，以本文件及上述专题文档为准。

## 全局速记（细节见专题文档）

- **API 不做版本化**，没有 `/api/v1/`；路由都在 `backend/app/routers/`（没有 `app/api/`）。
  前缀在 `main.py` 的 `include_router()` 指定，例外是 `audit_projects.py` /
  `project_agent.py` 自声明 `prefix="/api/audit-projects"`。
- **统一响应体** `{code, message, data, timestamp}`，从 `app/utils/response.py` 引入
  `make_response`（仍有 15 个路由留着本地副本，顺手换掉，别新增）。
- **数据库全异步**：`AsyncSession` + `await db.execute()` + `selectinload` + `Depends(get_db)`。
- **软删除**只对挂了 `SoftDeleteMixin` 的模型生效——不是所有表都有 `is_deleted`，
  盲加过滤会报字段不存在。带唯一约束的字段软删除时追加 `_deleted_<timestamp>` 后缀。
- **角色判断**统一走 `app/utils/roles.py`，不要硬编码 `role != "admin"`。
  角色：`super_admin` / `admin` / `expert` / `auditor`。
- **Agent 写回一律人在回路**：产出 `action_proposal` 确认卡，用户确认后才落库。
- **全局异常处理靠字符串匹配异常消息**归类（非法 UUID→404、约束冲突→409、其余→500），
  改异常文案前先确认不会打乱映射。
- 路径别名：前端 `@/` → `src/`；后端 `app.*` → `app/`。
- 上传文件用 UUID 名 + MIME 校验，落 `backend/uploads/`，静态挂 `/uploads`。
- 交互文档 `/api/docs`，ReDoc `/api/redoc`。
