# AGENTS.md

Guidelines for agentic coding agents working in this repository.

## Project Overview

专家现场工作辅助系统 (Expert Field Inspection System - EFIS) - A field inspection system with three components:
- **Backend**: FastAPI (Python 3.11+) with PostgreSQL + SQLAlchemy (async)
- **Web Admin**: React 18 + TypeScript + Ant Design + Vite
- **H5 Mobile App**: Vue 3 + Vant UI + Vite

## Build/Lint/Test Commands

### Backend (FastAPI)
```bash
cd backend
.venv\Scripts\activate                    # Windows: activate venv
pip install -r requirements.txt           # Install dependencies
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000  # Dev server
alembic upgrade head                      # Run migrations
alembic revision --autogenerate -m "description"  # Create migration
python -m pytest tests/ -v                # Run all tests
python -m pytest tests/test_file.py -v    # Run single test file
python -m pytest tests/test_file.py::test_name -v  # Run single test
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
**State**: Zustand stores in `stores/`, API calls in `services/api.ts`.
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

## Key Architecture Patterns

**Auth**: JWT `access_token` (8h) + `refresh_token` (30d). Use `Depends(get_current_user)` / `Depends(get_current_admin_user)`. Frontend sends `Authorization: Bearer <token>`.
**Audit**: All write operations auto-logged via `AuditMiddleware`.
**File uploads**: UUID filenames, MIME type validated, stored in `uploads/`.
**Path aliases**: `@/` in frontend, `app.` in backend.

## File Structure

```
backend/app/
├── models/      # SQLAlchemy ORM models
├── schemas/     # Pydantic request/response models
├── routers/     # FastAPI route handlers (prefix: /api/*)
├── services/    # Business logic (llm_service.py, etc.)
├── utils/       # Security (JWT), file handling
└── middleware/   # AuditMiddleware

web-admin/src/
├── pages/       # Route-based page components
├── components/  # Shared components (MainLayout)
├── stores/      # Zustand state (auth, app)
└── services/    # API client (api.ts)

h5-app/src/
├── views/       # Vue page components
├── api/         # API modules (JS)
├── utils/       # offlineStorage, uploadQueue, photoUtils
└── main.js      # Entry with Vant registration
```

## User Roles

`super_admin` → full access | `admin` → template/task mgmt | `expert` → execute inspections | `auditor` → read-only

## Database Migrations

After model changes: `cd backend && alembic revision --autogenerate -m "description" && alembic upgrade head`

## Environment Config

- `backend/.env` - DB creds, JWT secret, LLM API keys
- `web-admin/.env.development` / `.env.production` - `VITE_API_URL`
- `h5-app/.env.development` / `.env.production` - `VITE_API_URL`
