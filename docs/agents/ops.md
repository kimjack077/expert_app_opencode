# 环境、部署与测试

## 环境变量

配置类是 `backend/app/config.py`（pydantic `BaseSettings`，**不是** `app/core/config.py`）。
`DATABASE_URL`（asyncpg）与 `DATABASE_URL_SYNC`（alembic 用）由 PG_* 计算得出。
真实值在 `backend/.env`；`app/config.py` 里也留了默认值兜底。

**数据库**
`PG_HOST` · `PG_PORT` · `PG_DB` · `PG_USER` · `PG_PASSWORD`

**鉴权**
`SECRET_KEY` · `ALGORITHM`(HS256) · `ACCESS_TOKEN_EXPIRE_MINUTES`(480) ·
`REFRESH_TOKEN_EXPIRE_DAYS`(30) · `CORS_ORIGINS` ·
`AUTH_USER_CACHE_TTL_SECONDS`(60，鉴权用户进程内缓存 TTL，0=关闭)

**性能**
`DB_POOL_PRE_PING`(默认不设 = 自动判定)——连接池 checkout 探活。
线上 FastAPI 与 PG 同机走回环（成本 <1ms）→ 自动开启，保留 BUG-17 的断连防护；
本地开发连公网库（单次往返 50~800ms）→ 自动关闭，省掉每请求一次白付往返。
需要固定行为时可显式设 `true`/`false` 覆盖（关闭的代价：空闲连接被断开后首个请求
可能报错，重试即恢复；`pool_recycle=1800` 仍定时回收兜底）。

**LLM 主链路**
`LLM_PROVIDER` · `LLM_BASE_URL` · `LLM_MODEL` · `LLM_API_KEY` ·
`LLM_MAX_TOKENS` · `LLM_TEMPERATURE` · `LLM_TOP_P` · `LLM_TIMEOUT`(180s) ·
`LLM_ENABLE_THINKING`
备用链路：`LLM_BACKUP_BASE_URL` / `_MODEL` / `_API_KEY`（`utils/llm_fallback.py`）

**模型分层**（供 `app/agents/llm_gateway.py`）
`LLM_CHEAP_MODEL` · `LLM_STANDARD_MODEL`——留空则回退到 `LLM_MODEL`

**RAG / Embedding**
`EMBEDDING_BASE_URL` · `EMBEDDING_MODEL`(BAAI/bge-m3) · `EMBEDDING_API_KEY`
备选供应商：`NVIDIA_*`、`MINIMAX_*`

**多模态 / AI 提取**
`VISION_LLM_BASE_URL` / `_MODEL` / `_API_KEY`
`AI_EXTRACT_LLM_*`（含 `_BACKUP_*` 与 `_REASONING_EFFORT`）

**主动巡检**
`PROACTIVE_SCAN_INTERVAL_SECONDS`(1800) · `PROACTIVE_REAUDIT_DUE_DAYS`(330)

**上传**
`UPLOAD_DIR`(./uploads) · `MAX_FILE_SIZE`(10MB) · `PROJECT_DOCUMENT_MAX_FILE_SIZE`(50MB) · `DEBUG`

**前端**
`web-admin/.env.development|.env.production`、`h5-app/.env.development|.env.production`
里的 `VITE_API_URL`（默认 `http://localhost:8000`）。

## 测试

后端有两类测试文件，别混：

| 位置 | 性质 | 前置条件 |
|------|------|----------|
| `backend/tests/*.py` | 真单元测试（agent / llm / rag / report / 归档 / 存储路径 / 正式流同步） | 无需起服务 |
| `backend/test_mvp_api.py` | 冒烟，但直接驱动 FastAPI ASGI app | 无需起服务，pytest 安全 |
| `backend/test_all_crud.py` `test_comprehensive.py` `test_login*.py` | 手工冒烟脚本 | **需要** `http://localhost:8000` 在跑 |

```bash
cd backend && .venv\Scripts\activate     # pytest 只装在 venv 里，系统 Python 没有
python -m pytest tests/ -v
python -m pytest tests/test_rag_service.py -v
python -m pytest test_mvp_api.py -v
python test_all_crud.py                  # 需先起后端
```

根目录 `scripts/` 只保留数据维护与演示准备脚本（`db_health_check.py`、`check_orphan_data.py`、`archive_orphan_data.py`、
`audit_trail.py`、`compare_db_schema.py`、`demo_readiness_check.py`、`setup_new_demo_assets.py`、`reset_demo_task.py`、
`clear_db_records.py` 等）。早期的一次性探测 / 冒烟脚本（`probe_*`、`test_*`、`run_remote_*`、`full_system_e2e_test.py`、
`playwright_frontend_full_test.js` 等）已于 2026-11-23 移到根目录 `_已停用_可直接删除/临时测试文件/scripts/`。

前端没有测试脚本，校验手段是 `npx tsc --noEmit`（web-admin）/ `npm run type-check`（h5）。

⚠️ **本地测试写的是线上共享库**（见 [data-model.md](data-model.md)）。
`clear_db_records.py` 默认只**预演**（统计各表行数，不修改数据）；
加 `--apply` 才会真正 TRUNCATE 四张表（模板/模板项/检查记录/记录项）。

> [!IMPORTANT]
> 该脚本会清空全库的检查模板与检查记录——**对共享生产库严禁执行 `--apply`**。
> 清理冒烟测试数据应按创建时记录的 ID 精确删除
> （`DELETE /api/templates/{id}` · `/api/tasks/{id}` · `/api/audit-projects/{id}` ·
> `/api/enterprises/{id}`），不要整表清空。

## 部署（须用户明确指令）

> [!IMPORTANT]
> **严禁未经用户在当前对话中明确、单独的指令自动执行部署或 `git push`。**
> 代码改完只做本地构建与测试校验，然后在对话里汇报。

部署由仓库根目录的 Python 脚本驱动（没有 Docker，也没有 Makefile）：

| 脚本 | 范围 | 说明 |
|------|------|------|
| `fast_deploy.py` | 后端代码 + 两个前端 dist（可单选 `backend` / `web` / `h5`） | ✅ **日常首选**。前端需先在本地 `npm run build`；后端上传 `backend/app` 后 `systemctl restart expert-backend` |
| `deploy.py` | 全量：上传源码、服务器上 `npm install` + `npm run build`、重装 nginx 配置 | ✅ 改了依赖（`requirements.txt` / `package.json`）时用 |
| `scripts/deploy_backend_only.py` | 仅后端（nohup uvicorn 方式） | ⚠️ 备用。线上后端已改由 systemd `expert-backend` 管理，优先用 `fast_deploy.py backend` |

2026-11-23 起，`deploy_server.py`（会在服务器跑 alembic，禁用）、`deploy_web_admin.py`、`redeploy_h5.py`（目标机已不可达）、
`setup_nginx.py`、`update_frontend_serving.py`、`cleanup_server.py`、`upload_project_docs.py`、`deploy_h5_task_fix.py`，
以及旧拓扑的 `efis-backend.service` / `efis-nginx.conf`，已移到 `_已停用_可直接删除/旧部署脚本/`。

### 线上真实拓扑（2026-11-23）

```
49.232.213.79  /home/ubuntu/expert_app/
  backend/          systemd 单元 expert-backend（uvicorn :8000，Restart=always）
  web-admin/dist/   nginx :3000（配置见 deploy/nginx-easyaudit.conf）
  h5-app/dist/      nginx :5173，/h5/ 前缀映射回 dist 根
```

| 服务 | 地址 |
|------|------|
| 后端 API | `http://49.232.213.79:8000`（`/api/health` 应返回 200） |
| Web Admin | `http://49.232.213.79:3000` |
| H5 App | `http://49.232.213.79:5173/h5/` |

**访问方式是按端口直连，不是 80 端口。**
`backend/app/main.py` 里 `WEB_ADMIN_DIR = "/opt/efis/web-admin"` 的 SPA catch-all 永不生效（目录不存在），属遗留代码。

### 部署流程

```bash
cd web-admin && npm run build && cd ..    # 改了 Web 时
cd h5-app && npm run build && cd ..       # 改了 H5 时
python fast_deploy.py                     # 或 python fast_deploy.py backend / web / h5
```

`fast_deploy.py` 只上传有变化的文件（大小不同，或本地文件比服务器上的新）。

**核对后端是否真的换成了新代码**：打开 `http://49.232.213.79:8000/openapi.json` 看接口参数是否与本地一致。
若不一致，常见原因是 `deploy.py` 曾用 nohup 起过一个 uvicorn 占着 8000 端口，systemd 重启的新进程绑不上端口、
旧进程继续服务。排查：`sudo ss -ltnp | grep 8000`、`systemctl status expert-backend`，杀掉多余的 uvicorn 后再重启服务。

**任何情况下都不要跑数据库迁移**：本地与线上共库，迁移只在本地执行一次。

