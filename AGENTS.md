# AGENTS.md

Guidelines for agentic coding agents working in this repository.

## Project Overview

专家现场工作辅助系统 (Expert Field Inspection System - EFIS) - A field inspection system with three components:
- **Backend**: FastAPI (Python 3.11+) with PostgreSQL
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
python -m pytest tests/ -v                # Run all tests (if tests exist)
python -m pytest tests/test_file.py -v    # Run single test file
python -m pytest tests/test_file.py::test_name -v  # Run single test
```

### Web Admin (React)
```bash
cd web-admin
npm install                               # Install dependencies
npm run dev                               # Development server
npm run build                             # Production build (includes tsc)
npx tsc --noEmit                          # Type check only
```

### H5 App (Vue 3)
```bash
cd h5-app
npm install                               # Install dependencies
npm run dev                               # Development server
npm run build                             # Production build
npm run type-check                        # Type check (vue-tsc --build)
npm run format                            # Format with oxfmt
```

### Mobile App (React Native - if applicable)
```bash
cd mobile-app
npm install
npm run dev                               # Development server on port 3001
npm run build                             # Production build
```

## Code Style Guidelines

### Python (Backend)

**Imports**: Group imports in this order:
1. Standard library (alphabetically)
2. Third-party packages (alphabetically)
3. Local imports (from app.*)

```python
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
```

**Naming**:
- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Router instances: `router = APIRouter()`
- Schema classes: `*Base`, `*Create`, `*Update`, `*Response`

**Error Handling**:
- Use `HTTPException` with `status_code` and `detail`
- Always check user authorization before operations
- Use `result.scalar_one_or_none()` for single results

**Database**:
- Always use async: `AsyncSession`, `await db.execute()`
- Use `selectinload` for eager loading relationships
- Use `Depends(get_db)` for session injection

**Schemas**:
- Inherit from `BaseModel` for Pydantic schemas
- Use `Field(...)` for validation constraints
- Add `class Config: from_attributes = True` for response models

### TypeScript/React (Web Admin)

**Imports**: Group by type, use `@/` alias for src:
```typescript
import { useState, useEffect } from 'react'
import { Card, Table, Button } from 'antd'
import { useNavigate } from 'react-router-dom'
import { taskApi } from '@/services/api'
```

**Naming**:
- Components: `PascalCase` functions (export default)
- Variables/functions: `camelCase`
- Types/interfaces: `PascalCase`
- API objects: `xxxApi` (e.g., `taskApi`, `templateApi`)

**Components**:
- Use functional components with hooks
- Use `const [state, setState] = useState<Type>()`
- Destructure props in function signature

**State Management**:
- Zustand stores in `stores/` directory
- API calls in `services/api.ts`

**Ant Design**:
- Use Form component with `form.submit()` for submissions
- Use `message.success()`/`message.error()` for notifications

### Vue 3 (H5 App)

**Script Setup**:
```vue
<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const items = ref([])
const loading = ref(false)
</script>
```

**Naming**:
- Use `camelCase` for variables and functions
- Use `PascalCase` for component files
- API functions in separate files: `import { getTasks } from '../api/tasks.js'`

**Vant UI**:
- Use Vant components with `van-` prefix
- Use `van-pull-refresh` and `van-list` for infinite scroll

**CSS**:
- Use scoped styles with CSS variables
- Follow existing CSS variable naming: `--primary-color`, `--bg-white`, etc.

## Response Format (Backend)

All API responses use unified format:
```json
{
  "code": 200,
  "message": "success",
  "data": {...},
  "timestamp": "2026-01-01T00:00:00Z"
}
```

Use `ApiResponse` schema from `app/schemas`:
```python
def make_response(data=None, code=200, message="success"):
    return ApiResponse(
        code=code, message=message, data=data, timestamp=datetime.utcnow()
    )
```

## Authentication

- JWT tokens: `access_token` (8 hours), `refresh_token` (30 days)
- Use `Depends(get_current_user)` for protected routes
- Use `Depends(get_current_admin_user)` for admin-only routes
- Frontend sends `Authorization: Bearer <token>`

## User Roles

- `super_admin` - Full system access
- `admin` - Template/task management
- `expert` - Execute inspections (mobile app primary user)
- `auditor` - Read-only access

## File Structure Conventions

```
backend/app/
├── models/      # SQLAlchemy ORM models
├── schemas/     # Pydantic request/response models
├── routers/     # FastAPI route handlers
├── services/    # Business logic (LLM, etc.)
├── utils/       # Security, file handling
└── middleware/  # Request middleware

web-admin/src/
├── pages/       # Page components (route-based)
├── components/  # Shared components
├── stores/      # Zustand state management
└── services/    # API client

h5-app/src/
├── views/       # Vue page components
├── components/  # Shared Vue components
├── api/         # API modules
└── utils/       # Utilities (offline storage, etc.)
```

## Database Migrations

After model changes:
```bash
cd backend
alembic revision --autogenerate -m "description of change"
alembic upgrade head
```

## Important Patterns

1. **Async/Await**: All database operations are async
2. **Dependency Injection**: Use FastAPI `Depends()` for DB sessions and auth
3. **Audit Logging**: Automatic via `AuditMiddleware` for all write operations
4. **Path Aliases**: Use `@/` in frontend, `app.` in backend
5. **UUID Primary Keys**: All models use UUID for IDs