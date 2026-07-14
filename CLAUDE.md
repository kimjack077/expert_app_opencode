# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

专家现场工作辅助系统 (Expert Field Inspection System - EFIS) - A system for field inspection experts to conduct inspections, record results, and receive AI-powered regulatory suggestions.

**Architecture**: Multi-tier application with multiple clients
- **Backend**: FastAPI (Python 3.11+) with PostgreSQL
- **Web Admin**: React 18 + TypeScript + Ant Design + Vite
- **H5 Mobile App**: Vue 3 + Vant UI + Vite (for field inspectors, base path `/h5/`)
- **Mobile App**: React 18 + TypeScript + antd-mobile + Vite (port 3001)
- **Inspection App (Flutter)**: Flutter 3.x + Riverpod (in development)

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
# Tests (no tests/ dir - test files live at backend/test_*.py)
python -m pytest test_mvp_api.py -v         # Run one test file
python -m pytest test_mvp_api.py::test_health_endpoint -v  # Run one test
```
Note: `pytest` must be run from the activated `.venv` (it is not installed in the system Python). `test_mvp_api.py` uses FastAPI's ASGI app directly for pytest-safe checks; other `test_*.py` files are manual smoke scripts that expect a running server at `http://localhost:8000`.

### Web Admin (React)
```bash
cd web-admin
npm install
npm run dev      # Development server (uses .env.development)
npm run build    # Production build
```

### H5 App (Vue 3)
```bash
cd h5-app
npm install
npm run dev      # Development server (uses .env.development)
npm run build    # Production build
npm run type-check  # TypeScript type checking (vue-tsc)
npm run format   # Format code with oxfmt
```

**Node version requirement**: `^20.19.0 || >=22.12.0`

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
- `MINIMAX_*` - Alternative LLM provider configuration

## Project Structure

```
backend/app/models/
├── user.py           # User, Organization
├── template.py       # InspectionTemplate, TemplateItem
├── task.py           # InspectionTask, TaskItemRecord
├── record.py         # InspectionRecord, InspectionRecordItem
├── enterprise.py     # Enterprise and related entities
├── media.py          # MediaFile
├── audit.py          # AuditLog, LLMCallLog
├── knowledge.py      # Knowledge management
├── audit_project.py  # AuditProject, AuditTeamMember, AuditPlanItem, Nonconformity, etc.
├── rag.py            # KnowledgeEmbedding, AgentMemory, PhotoAnalysis
└── industry.py       # Industry classification

backend/app/services/
├── llm_service.py      # LLM integration (suggestions, basis, final judgment)
├── ai_extract_service.py # AI-assisted document parsing
├── audit_agent.py      # AI agent for audit preparation and report generation
└── report_generator.py # Word/PDF report generation

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
- `AuditReport` - Report with Word/PDF export via `/api/v1/audit-projects/{id}/export/word|pdf`

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

### H5 App Offline Support
- `offlineStorage.js` - Local storage for task data
- `uploadQueue.js` - Queue for failed photo uploads with retry
- All check results saved locally before sync
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
| `/api/v1/audit-projects` | Audit project management (certification audits) |
| `/api/health` | Health check endpoint |

## Important Conventions

1. **Async database operations**: All DB operations use SQLAlchemy async session
2. **Dependency injection**: Use `Depends(get_db)` for database sessions, `Depends(get_current_user)` for auth
3. **Audit logging**: All write operations automatically logged via `AuditMiddleware`
4. **File uploads**: Stored with UUID filenames, validated by MIME type
5. **Mobile-first for h5-app**: Uses Vant UI components, optimized for touch interaction
6. **H5 base path**: `/h5/` - configured in Vue router and backend static file serving
7. **API response format**: All endpoints return `{code, message, data, timestamp}` structure

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

## Production Deployment

Backend serves both frontends:
- `/` → Web Admin (from `/opt/efis/web-admin`)
- `/h5` → H5 App (from `/opt/efis/h5-app`)
- `/api` → Backend API
- `/uploads` → Static file serving

## Security Note

**Do not commit sensitive credentials.** The `dev guides.md` file contains database credentials and API keys for reference only. Use environment variables (`.env` files) for actual configuration, and ensure `.env` is in `.gitignore`.