# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

专家现场工作辅助系统 (Expert Field Inspection System - EFIS) - A system for field inspection experts to conduct inspections, record results, and receive AI-powered regulatory suggestions.

**Architecture**: Multi-tier application with multiple clients
- **Backend**: FastAPI (Python 3.11+) with PostgreSQL
- **Web Admin**: React 18 + TypeScript + Ant Design + Vite
- **H5 Mobile App**: Vue 3 + Vant UI + Vite (for field inspectors, base path `/h5/`)
- **Mobile App**: React 18 + TypeScript + antd-mobile + Vite (port 3001)
- **Inspection App (Flutter)**: Flutter 3.x + Riverpod + Dio/Retrofit + GoRouter (in development)

> A companion **`AGENTS.md`** at the repo root is a short index of hard constraints plus pointers into five topic docs under `docs/agents/` — `backend.md` (router map, service map, cross-cutting conventions, Python style), `frontend.md` (three clients' structure and style), `data-model.md` (table map, soft-delete scope, the three-parallel-record-models debt, migration flow), `ai-agent.md` (shared agent runtime, tool loop, evidence pipeline, endpoints), `ops.md` (env vars, tests, deployment). Read the relevant topic doc before writing backend or frontend code.

## Development Commands

### Backend (FastAPI)
```bash
cd backend
# Activate virtual environment (Windows)
.venv\Scripts\activate
# Install dependencies
pip install -r requirements.txt
# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"
# Tests
python -m pytest tests/ -v                   # Unit tests (backend/tests/: agent/llm/rag/report/audit services)
python -m pytest tests/test_rag_service.py -v # Run one test file
python -m pytest test_mvp_api.py -v          # pytest-safe smoke test (uses ASGI app directly, no server needed)
python test_all_crud.py                      # Comprehensive CRUD smoke script (needs running server)
```
Note: `pytest` must be run from the activated `.venv` (it is not installed in the system Python). Two kinds of test files coexist: `backend/tests/*.py` are unit tests, and `backend/test_*.py` at the root are mostly manual smoke scripts that expect a running server at `http://localhost:8000` (except `test_mvp_api.py`, which drives the FastAPI ASGI app directly and is pytest-safe).

### Web Admin (React)
```bash
cd web-admin
npm install
npm run dev      # Development server on port 3000 (uses .env.development)
npm run build    # Production build (tsc && vite build)
npx tsc --noEmit # Type check only (no dedicated lint/test scripts)
```
Vite dev proxies `/api` and `/uploads` to `http://localhost:8000`. `@` aliases `src/`.

### H5 App (Vue 3)
```bash
cd h5-app
npm install
npm run dev      # Development server on port 5174 (uses .env.development)
npm run build    # Production build (runs type-check + vite build)
npm run type-check  # TypeScript type checking (vue-tsc --build)
npm run format   # Format code with oxfmt (no semicolons, single quotes)
```

**Node version requirement**: `^20.19.0 || >=22.12.0`
Vite dev proxies `/api` and `/uploads` to `http://localhost:8000`. `@` aliases `src/`. Base path is `/h5/`.

### Mobile App (React)
```bash
cd mobile-app
npm install
npm run dev      # Development server on port 3001
npm run build    # Production build
```

### Inspection App (Flutter)
```bash
cd inspection_app
flutter pub get          # Install dependencies
flutter run              # Development (select device)
flutter build apk        # Build Android APK
flutter build appbundle  # Build Android App Bundle
flutter build ios        # Build iOS
```
**Flutter SDK requirement**: `>=3.0.0`

## Environment Configuration

Each module has its own environment configuration:
- `backend/.env` - Backend settings (database, JWT, LLM)
- `web-admin/.env.development` / `.env.production` - Frontend API URL
- `h5-app/.env.development` / `.env.production` - H5 API URL

Key environment variables:
- `VITE_API_URL` - Backend API URL (default: `http://localhost:8000`)
- `PG_HOST`, `PG_PORT`, `PG_DB`, `PG_USER`, `PG_PASSWORD` - PostgreSQL connection
- `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` - LLM service configuration
- `LLM_TIMEOUT` - LLM request timeout (default: 180 seconds)
- `LLM_MAX_TOKENS`, `LLM_TEMPERATURE`, `LLM_TOP_P`, `LLM_ENABLE_THINKING` - LLM tuning
- `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`, `EMBEDDING_API_KEY` - RAG embeddings (e.g. BAAI/bge-m3)
- `VISION_LLM_BASE_URL`, `VISION_LLM_MODEL`, `VISION_LLM_API_KEY` - multimodal/photo analysis
- `MINIMAX_*`, `NVIDIA_*` - Alternative LLM/embedding providers

## Project Structure

```
backend/app/
├── config.py         # pydantic BaseSettings (NOT app/core/config.py); DATABASE_URL (asyncpg) + DATABASE_URL_SYNC (alembic) are computed
├── routers/          # FastAPI route handlers (all routes; there is no app/api/)
├── schemas/          # Pydantic request/response models
├── middleware/       # AuditMiddleware (logs writes to AuditLog)
└── utils/            # security (JWT), file_handler, soft_delete

backend/app/models/
├── user.py           # User, Organization
├── template.py       # InspectionTemplate, TemplateItem
├── task.py           # InspectionTask, TaskItemRecord
├── record.py         # InspectionRecord, InspectionRecordItem
├── enterprise.py     # Enterprise, EnterpriseQualification/Product/Equipment/Personnel, RectificationRecord
├── media.py          # MediaFile
├── audit.py          # AuditLog, LLMCallLog
├── knowledge.py      # KnowledgeDocument, InspectionGuideline
├── audit_project.py  # AuditProject, AuditTeamMember, AuditPlanItem, AuditArea, AuditAreaRecord, Nonconformity, AuditReport, CommunicationMeeting
├── rag.py            # KnowledgeEmbedding, CheckItemRegulation, AgentMemory, TemplateRecommendation, PhotoAnalysis
├── agent_conversation.py  # AgentConversation, AgentMessage
├── project_knowledge.py   # ProjectDocument, ProjectKnowledgeChunk
├── evidence_agent.py      # AiAuditSession, EvidenceSubmission, EvidenceItem, AiDraftRecord
├── project_artifact.py    # ProjectArtifact
└── industry.py       # Industry classification

backend/app/services/
├── llm_service.py      # LLM integration (suggestions, basis, final judgment)
├── rag_service.py      # RAG retrieval over knowledge embeddings
├── agent_service.py    # AI assistant conversation service
├── audit_agent.py      # Audit-preparation / report-generation agent
├── evidence_agent_service.py # Evidence-collection agent
├── multimodal_service.py     # Vision/multimodal AI (photo analysis)
├── ai_extract_service.py     # AI-assisted document parsing / template extraction
├── project_knowledge_service.py / project_document_parser.py / project_artifact_service.py  # Project doc & artifact pipeline
├── report_generator.py / report_service.py  # Word/PDF report generation
├── template_recommendation_service.py  # Template recommendation
├── project_access_service.py # Project-level access control
└── formal_audit_sync_service.py  # Sync audit plan items ↔ inspection tasks

web-admin/src/
├── pages/                # Page components
├── components/           # Shared components (MainLayout)
├── stores/               # Zustand state (auth, app)
└── services/api.ts       # Axios API client

h5-app/src/
├── views/                # Vue views
├── api/                  # API modules (auth, tasks, records, media) - JavaScript
├── utils/                # photoUtils.js, offlineStorage.js, uploadQueue.js
└── main.js               # Vue app entry with Vant components

mobile-app/src/
├── pages/                # Page components (Login, TaskList, QuickCheck, Profile, Inspection)
├── components/           # Shared components (BottomNav)
├── services/api.ts       # Axios API client
└── stores/auth.ts        # Zustand state

inspection_app/lib/
├── models/               # Data models
├── screens/              # Page screens
├── services/             # API service layer
├── providers/            # State management (Riverpod)
├── router/               # GoRouter configuration
└── theme/                # App theme

## Backend Dependencies

Core packages (see `backend/requirements.txt`):
- **FastAPI + Uvicorn** - Web framework and server
- **SQLAlchemy + asyncpg + Alembic** - Async ORM and migrations
- **python-jose + passlib** - JWT and password hashing
- **openai** - LLM client (compatible with various providers)
- **redis** - Caching and session storage
- **Document processing**: PyMuPDF (PDF), python-docx (Word), openpyxl (Excel), reportlab (PDF generation)
- **Pillow** - Image processing

## Key Architecture Patterns

### Backend API Response Format
All endpoints return unified format:
```json
{
  "code": 200,
  "message": "success",
  "data": {...},
  "timestamp": "2026-01-01T00:00:00Z"
}
```

### Authentication Flow
- JWT tokens: `access_token` (8 hours), `refresh_token` (30 days)
- Authorization header: `Bearer <access_token>`
- Auto-refresh on 401 response in web-admin and h5-app
- Route guard in h5-app checks localStorage token

### Database Models - Key Relationships
```
# Inspection workflow
InspectionTemplate → TemplateItem (one-to-many)
InspectionTask → TaskItemRecord (one-to-many)
TaskItemRecord → TemplateItem (links to check item)
MediaFile → InspectionTask or TaskItemRecord (optional link)
Enterprise → EnterpriseQualification, EnterpriseProduct, EnterpriseEquipment, etc.

# Audit project workflow (certification audits)
AuditProject → AuditTeamMember, AuditPlanItem, AuditArea, AuditAreaRecord, Nonconformity, AuditReport, CommunicationMeeting
AuditPlanItem → InspectionTask (auto-created when plan item is created)
AuditAreaRecord → InspectionRecordItem (check item results)
```

### LLM Integration (services/llm_service.py)
Three prompt types:
1. `SUGGESTION_PROMPT` - Generate inspection conclusion based on check item and result
2. `BASIS_PROMPT` - Provide regulatory/legal basis for check items
3. `FINAL_JUDGMENT_PROMPT` - Generate overall inspection result summary

Features:
- Streaming API support for real-time response display
- Result caching in `TaskItemRecord.llm_suggestion` and `llm_basis`
- All calls logged to `LLMCallLog` table

### Audit Project Workflow (Certification Audits)
The system supports two workflows:
1. **Simple Inspection**: InspectionTask → TaskItemRecord → InspectionRecordItem
2. **Certification Audit**: AuditProject → AuditPlanItem → InspectionTask (auto-created)

Key audit project entities:
- `AuditProject` - Top-level container for certification audits (initial, surveillance, recertification)
- `AuditPlanItem` - Work task unit; creates `InspectionTask` automatically when created
- `AuditAreaRecord` - Collaborative field record with multiple co-recorders
- `Nonconformity` - Tracks issues with severity levels (major/minor/observation)
- `AuditReport` - Report with Word/PDF export via `/api/audit-projects/{id}/export/word|pdf`

### AI Agent Features (services/audit_agent.py)
- `prepare_audit_with_ai` - AI audit preparation suggestions
- `evaluate_evidence_with_ai` - Evidence sufficiency assessment
- `generate_report_with_ai` - Generate narrative evaluation text
- `suggest_nc_with_ai` - Suggest nonconformity based on evidence

### User Roles
- `super_admin` - Full system access
- `admin` - Template/task management
- `expert` - Execute inspections (mobile app primary user)
- `auditor` - Read-only access

### H5 App Offline Support (mostly REMOVED — verify before relying on it)
- **There is no offline write queue or local record persistence.** `src/utils/` contains only `display.js` and `photoUtils.js`; the previously documented `offlineStorage.js` / `uploadQueue.js` no longer exist.
- The only offline handling is `components/OfflineBanner.vue`, which watches `navigator.onLine` and shows a banner. It does not buffer or retry writes.
- The Agent path (SSE + remote LLM) is **online-only**, so the AI copilot is unavailable with no signal.
- Request interceptor (`request.js`) handles 401 by clearing token and redirecting to `/login`

## API Endpoints

| Prefix | Purpose |
|--------|---------|
| `/api/auth` | Login, logout, token refresh, user info |
| `/api/templates` | Inspection templates and items management |
| `/api/tasks` | Task CRUD, start/complete, records management |
| `/api/records` | Inspection records management |
| `/api/media` | File upload and management |
| `/api/llm` | AI suggestions, legal basis, final judgment (with streaming) |
| `/api/analytics` | Dashboard stats, audit logs |
| `/api/enterprises` | Enterprise management module |
| `/api/knowledge` | Knowledge base management |
| `/api/ai-extract` | AI-assisted template extraction from documents (PDF/Word/Excel) |
| `/api/industries` | Industry classification |
| `/api/users` | User management |
| `/api/agent` | AI assistant endpoints |
| `/api/ai-enhanced` | AI enhanced features (photo analysis, etc.) |
| `/api/statistics` | Audit statistics dashboard |
| `/api/audit-projects` | Audit project management (certification audits) — `project_agent.py` also mounts nested routes under this prefix |
| `/api/health` | Health check endpoint |

**Note**: The API is **not versioned** — there is no `/api/v1/`. All routers mount flat under `/api/<resource>`. Routers live in `backend/app/routers/` (there is no `app/api/` package). Prefixes are set at `include_router()` in `main.py`, except `audit_projects.py` and `project_agent.py`, which self-declare `prefix="/api/audit-projects"`. Interactive docs at `/api/docs`, ReDoc at `/api/redoc`.

## Important Conventions

1. **Async database operations**: All DB operations use SQLAlchemy async session
2. **Dependency injection**: Use `Depends(get_db)` for database sessions, `Depends(get_current_user)` / `Depends(get_current_admin_user)` for auth
3. **Audit logging**: All write operations automatically logged via `AuditMiddleware`
4. **File uploads**: Stored with UUID filenames, validated by MIME type; live in `backend/uploads/`, served statically at `/uploads`
5. **Mobile-first for h5-app**: Uses Vant UI components, optimized for touch interaction
6. **H5 base path**: `/h5/` - configured in Vue router and backend static file serving
7. **API response format**: All endpoints return `{code, message, data, timestamp}` via `make_response()`
8. **Soft delete**: Business entities use soft delete (`SoftDeleteMixin` adds `is_deleted` + `deleted_at`; helpers in `app/utils/soft_delete.py`). Queries must filter `is_deleted == False`. When soft-deleting a row with a unique field (e.g. `code`, `project_no`), append a `_deleted_<timestamp>` suffix to avoid future unique-constraint collisions. `audit_logs` is never soft-deleted.
9. **Global exception handler** (`main.py`) maps errors by string-matching the exception message: invalid UUID → 404, FK/unique violation → 409, else 500. Be careful changing exception messages.

## Shared Remote Database (important)

**Local development and the deployed server use the SAME remote PostgreSQL** (`PG_HOST=49.232.213.79`, `PG_DB=db_expert_claude`). Consequences:
- **Migrations run once, locally.** After a model change: `cd backend && alembic revision --autogenerate -m "..." && alembic upgrade head`. Deploy does **not** re-run migrations (the DB is already updated).
- **Local tests mutate production data.** Smoke scripts / manual tests write to the live shared DB — clean up test data afterward (`scripts/clear_db_records.py`).
- The connection default is also hardcoded in `app/config.py`, and `backend/.env` currently contains real DB/LLM/embedding secrets — do not add new secrets to committed files.

## LLM Service Usage

When calling LLM from frontend:
```javascript
// Streaming API example
const response = await fetch(`${API_URL}/api/llm/suggestion/stream`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
  body: JSON.stringify({ task_id, record_id, use_cache: true })
})
const reader = response.body.getReader()
// Read stream chunks...
```

## Template Item Types

Template items support multiple check types via `check_type` field:
- `radio` - Pass/fail/NA selection
- `checkbox` - Multiple choice
- `text` - Free text input
- `number` - Numeric input with min/max range
- `score` - Score input with pass threshold
- `photo` - Photo capture required

## Production Deployment & Git Rules

> [!IMPORTANT]
> **【安全铁律】严禁未经用户明确指令自动部署或推送到 GitHub**：
> 1. **严禁自动部署**：除非用户在对话中明确、单独指定“部署到服务器 / 运行 deploy”，否则任何代码修改后**严禁自动运行 `python deploy.py` 或任何部署脚本**。
> 2. **严禁自动推送 GitHub**：除非用户明确指定“推送到 GitHub / git push”，否则**严禁自动执行 `git push`**。
> 3. 代码修改后仅在本地完成测试与构建校验（如 `npm run build`、`pytest`），并在对话中向用户汇报。

Deployment is driven by **Python scripts at the repo root** (no Docker/Makefile): `deploy.py` (full), plus targeted scripts `deploy_server.py`, `deploy_web_admin.py`, `redeploy_h5.py`, `setup_nginx.py`, `update_frontend_serving.py`. Infra config lives at root: `efis-backend.service` (systemd), `efis-nginx.conf` (nginx).

When explicitly requested by the user: commit to GitHub → `python deploy.py` (**skips DB migrations** — see Shared Remote Database) → verify at `http://49.232.213.79` (API `:8000`, Web Admin `:3000`, H5 `:5173`).

On the deployed Linux host the backend serves both frontends via a catch-all in `main.py`:
- `/` → Web Admin (from `/opt/efis/web-admin`)
- `/h5` → H5 App (from `/opt/efis/h5-app`)
- `/api` → Backend API (unmatched `/api/*` returns 404 JSON)
- `/uploads` → Static file serving

Note: the `/opt/efis/...` paths are Linux deploy paths and do not exist on the Windows dev box; the SPA catch-all only matters in production.

## Security Note

**Do not commit sensitive credentials.** The `dev guides.md` file contains database credentials and API keys for reference only. Use environment variables (`.env` files) for actual configuration, and ensure `.env` is in `.gitignore`.