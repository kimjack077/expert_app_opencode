# 专家现场工作辅助系统 — AI Agent 开发指南

**版本**: v1.0
 **日期**: 2026-02-23
 **用途**: 指导 AI Agent 完成完整系统的开发工作

------

## 目录

1. [项目概述](https://claude.ai/chat/45c613f9-2d43-4deb-8d6b-7ab80ce6d6d5#1-项目概述)
2. [技术栈选型](https://claude.ai/chat/45c613f9-2d43-4deb-8d6b-7ab80ce6d6d5#2-技术栈选型)
3. [系统架构设计](https://claude.ai/chat/45c613f9-2d43-4deb-8d6b-7ab80ce6d6d5#3-系统架构设计)
4. [数据库设计](https://claude.ai/chat/45c613f9-2d43-4deb-8d6b-7ab80ce6d6d5#4-数据库设计)
5. [后端开发规范](https://claude.ai/chat/45c613f9-2d43-4deb-8d6b-7ab80ce6d6d5#5-后端开发规范)
6. [前端APP开发规范](https://claude.ai/chat/45c613f9-2d43-4deb-8d6b-7ab80ce6d6d5#6-前端app开发规范)
7. [Web管理平台开发规范](https://claude.ai/chat/45c613f9-2d43-4deb-8d6b-7ab80ce6d6d5#7-web管理平台开发规范)
8. [LLM集成规范](https://claude.ai/chat/45c613f9-2d43-4deb-8d6b-7ab80ce6d6d5#8-llm集成规范)
9. [用户权限与安全](https://claude.ai/chat/45c613f9-2d43-4deb-8d6b-7ab80ce6d6d5#9-用户权限与安全)
10. [部署与运行环境](https://claude.ai/chat/45c613f9-2d43-4deb-8d6b-7ab80ce6d6d5#10-部署与运行环境)
11. [开发阶段规划](https://claude.ai/chat/45c613f9-2d43-4deb-8d6b-7ab80ce6d6d5#11-开发阶段规划)
12. [API接口规范](https://claude.ai/chat/45c613f9-2d43-4deb-8d6b-7ab80ce6d6d5#12-api接口规范)
13. [附录：配置信息](https://claude.ai/chat/45c613f9-2d43-4deb-8d6b-7ab80ce6d6d5#13-附录配置信息)

------

## 1. 项目概述

### 1.1 系统名称

**专家现场工作辅助系统**（Expert Field Inspection System，简称 EFIS）

### 1.2 核心目标

为现场专家（检查员、审查员、监管员等）提供一套数字化工具，支持：

- 按照法规、标准开展现场检查、审查、监管工作
- 结构化记录检查结果、审查意见、监管情况和现场照片
- 通过 LLM 实时获取监管建议和法规依据
- 后端管理平台供管理员配置检查模板、查看和分析操作数据

### 1.3 用户角色

| 角色       | 说明                                  | 主要端       |
| ---------- | ------------------------------------- | ------------ |
| 超级管理员 | 系统配置、用户管理、全量数据查看      | Web 管理平台 |
| 普通管理员 | 检查模板配置、任务分配、数据分析      | Web 管理平台 |
| 现场专家   | 执行检查任务、记录结果、获取 LLM 建议 | 移动端 APP   |
| 只读审计员 | 查看历史记录和报告                    | Web 管理平台 |

### 1.4 系统边界

```
┌─────────────────────────────────────────────────────┐
│                   EFIS 系统边界                       │
│                                                     │
│  ┌──────────────┐     ┌──────────────────────────┐  │
│  │  移动端 APP   │────▶│   后端 API 服务           │  │
│  │ (React Native│     │ (FastAPI / Python)        │  │
│  │  或 Flutter) │     │                          │  │
│  └──────────────┘     │  ┌────────────────────┐  │  │
│                       │  │  PostgreSQL DB      │  │  │
│  ┌──────────────┐     │  └────────────────────┘  │  │
│  │ Web 管理平台  │────▶│                          │  │
│  │  (React)     │     │  ┌────────────────────┐  │  │
│  └──────────────┘     │  │  文件存储 (本地/OSS) │  │  │
│                       │  └────────────────────┘  │  │
│                       └──────────────────────────┘  │
│                                    │                 │
│                                    ▼                 │
│                       ┌──────────────────────────┐  │
│                       │  NVIDIA API (DeepSeek V3) │  │
│                       └──────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

------

## 2. 技术栈选型

### 2.1 后端

| 组件     | 技术选型                      | 说明                          |
| -------- | ----------------------------- | ----------------------------- |
| Web 框架 | **FastAPI (Python 3.11+)**    | 高性能异步、自动 OpenAPI 文档 |
| ORM      | **SQLAlchemy 2.0 + asyncpg**  | 异步 PostgreSQL 操作          |
| 数据迁移 | **Alembic**                   | 数据库版本管理                |
| 认证     | **JWT (python-jose)**         | 无状态令牌认证                |
| 文件处理 | **python-multipart + Pillow** | 图片上传和压缩                |
| 任务队列 | **Celery + Redis**（可选）    | 异步任务、报告生成            |
| LLM 调用 | **openai Python SDK**         | 兼容 NVIDIA API 格式          |
| 数据验证 | **Pydantic v2**               | 请求/响应模型                 |

### 2.2 前端移动端 APP

| 组件        | 技术选型                                | 说明                            |
| ----------- | --------------------------------------- | ------------------------------- |
| 框架        | **React Native (Expo)**                 | 跨平台（iOS/Android），快速迭代 |
| 状态管理    | **Zustand**                             | 轻量状态管理                    |
| HTTP 客户端 | **Axios**                               | 请求拦截、Token 刷新            |
| 相机/媒体   | **expo-camera / expo-image-picker**     | 现场照片采集                    |
| 本地存储    | **AsyncStorage + SQLite (expo-sqlite)** | 离线缓存支持                    |
| UI 组件     | **React Native Paper**                  | Material Design 风格            |
| 表单        | **React Hook Form**                     | 复杂检查表单处理                |

### 2.3 Web 管理平台

| 组件     | 技术选型                  | 说明               |
| -------- | ------------------------- | ------------------ |
| 框架     | **React 18 + TypeScript** | 类型安全、生态完善 |
| UI 库    | **Ant Design 5**          | 企业级管理后台组件 |
| 状态管理 | **Zustand**               | 轻量简洁           |
| 路由     | **React Router v6**       | 嵌套路由、权限守卫 |
| HTTP     | **Axios**                 | 统一请求封装       |
| 图表     | **ECharts / Recharts**    | 数据分析可视化     |
| 构建工具 | **Vite**                  | 快速构建           |

### 2.4 基础设施

| 组件     | 技术                                         |
| -------- | -------------------------------------------- |
| 数据库   | PostgreSQL 14+（远程，见配置）               |
| 缓存     | Redis（Token黑名单、Session缓存）            |
| 文件存储 | 本地文件系统（初期）/ 对象存储（扩展）       |
| 运行环境 | Python 虚拟环境（.venv），Uvicorn + Gunicorn |
| 反向代理 | Nginx（静态资源 + API 转发）                 |

------

## 3. 系统架构设计

### 3.1 目录结构

```
efis/
├── .venv/                          # Python 虚拟环境
├── backend/                        # 后端服务
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口
│   │   ├── config.py               # 配置管理（环境变量）
│   │   ├── database.py             # 数据库连接池
│   │   ├── models/                 # SQLAlchemy ORM 模型
│   │   │   ├── user.py
│   │   │   ├── inspection.py       # 检查相关模型
│   │   │   ├── template.py         # 检查模板模型
│   │   │   ├── task.py             # 任务模型
│   │   │   └── media.py            # 照片/附件模型
│   │   ├── schemas/                # Pydantic 请求/响应模型
│   │   ├── routers/                # API 路由
│   │   │   ├── auth.py             # 认证接口
│   │   │   ├── users.py            # 用户管理
│   │   │   ├── templates.py        # 检查模板管理
│   │   │   ├── tasks.py            # 检查任务
│   │   │   ├── inspections.py      # 检查记录
│   │   │   ├── media.py            # 文件上传
│   │   │   └── llm.py              # LLM 建议接口
│   │   ├── services/               # 业务逻辑层
│   │   │   ├── auth_service.py
│   │   │   ├── template_service.py
│   │   │   ├── inspection_service.py
│   │   │   └── llm_service.py      # LLM 调用封装
│   │   ├── middleware/             # 中间件
│   │   │   ├── auth_middleware.py  # JWT 验证
│   │   │   └── audit_middleware.py # 操作日志记录
│   │   └── utils/
│   │       ├── security.py         # 密码加密、JWT 工具
│   │       └── file_handler.py     # 文件处理
│   ├── alembic/                    # 数据库迁移
│   ├── requirements.txt
│   └── .env                        # 环境变量（不提交到 git）
│
├── web-admin/                      # Web 管理平台 (React)
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Login/
│   │   │   ├── Dashboard/          # 数据概览
│   │   │   ├── Templates/          # 检查模板管理
│   │   │   ├── Tasks/              # 任务管理
│   │   │   ├── Records/            # 检查记录查看
│   │   │   ├── Users/              # 用户管理
│   │   │   └── Analytics/          # 数据分析
│   │   ├── components/
│   │   ├── stores/                 # Zustand 状态
│   │   ├── services/               # API 调用
│   │   └── router/
│   ├── package.json
│   └── vite.config.ts
│
├── mobile-app/                     # 移动端 APP (React Native)
│   ├── src/
│   │   ├── screens/
│   │   │   ├── Login/
│   │   │   ├── TaskList/           # 任务列表
│   │   │   ├── Inspection/         # 检查执行主界面
│   │   │   ├── CheckItem/          # 单条检查项
│   │   │   ├── PhotoCapture/       # 拍照记录
│   │   │   └── Report/             # 检查报告预览
│   │   ├── components/
│   │   ├── stores/
│   │   ├── services/
│   │   └── navigation/
│   └── package.json
│
├── nginx/
│   └── nginx.conf
└── docker-compose.yml（可选）
```

### 3.2 数据流设计

```
【检查模板配置流程】
管理员 → Web管理平台 → API → 数据库
  ① 创建检查标准分类（如：消防安全/电气设备/...）
  ② 在分类下创建多级检查条目（支持树形层级）
  ③ 创建检查模板，从条目库选取条目组合
  ④ 将模板绑定到检查任务

【现场检查执行流程】
专家 → 移动端APP → API → 数据库
  ① 登录，获取分配给自己的检查任务
  ② 打开任务，加载检查模板（含所有条目）
  ③ 逐条录入检查结果（合格/不合格/不适用 + 说明）
  ④ 点击"建议"→ 调用LLM → 返回监管建议
  ⑤ 点击"依据"→ 调用LLM → 返回法规标准依据
  ⑥ 拍照上传，关联到具体检查条目
  ⑦ 提交检查任务，生成检查报告

【管理员分析流程】
管理员 → Web管理平台 → API → 数据库
  ① 查看所有专家的操作记录（时间线）
  ② 数据统计分析（不合格率、高频问题等）
  ③ 导出检查报告
```

------

## 4. 数据库设计

### 4.1 连接配置

```python
# backend/app/config.py
DATABASE_CONFIG = {
    "host": "117.72.77.52",
    "port": 5432,
    "database": "db_expert_opencode",
    "user": "db_admin",
    "password": "1234567890@sdtj",
}

# 异步连接字符串
DATABASE_URL = "postgresql+asyncpg://db_admin:1234567890%40sdtj@117.72.77.52:5432/db_expert_opencode"
```

### 4.2 核心数据表设计

#### 用户表 `users`

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(50) UNIQUE NOT NULL,
    email           VARCHAR(100) UNIQUE,
    phone           VARCHAR(20),
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(100),
    role            VARCHAR(20) NOT NULL DEFAULT 'expert',
    -- 角色: super_admin / admin / expert / auditor
    org_id          UUID REFERENCES organizations(id),
    is_active       BOOLEAN DEFAULT TRUE,
    last_login_at   TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 机构表 `organizations`

```sql
CREATE TABLE organizations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(200) NOT NULL,
    code        VARCHAR(50) UNIQUE,
    description TEXT,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 检查标准分类表 `standard_categories`（树形结构）

```sql
CREATE TABLE standard_categories (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(200) NOT NULL,
    code        VARCHAR(50),
    parent_id   UUID REFERENCES standard_categories(id),  -- 支持多级
    level       INTEGER NOT NULL DEFAULT 1,               -- 层级深度
    sort_order  INTEGER DEFAULT 0,
    description TEXT,
    legal_basis TEXT,    -- 法规依据（给LLM参考）
    created_by  UUID REFERENCES users(id),
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 检查条目表 `check_items`

```sql
CREATE TABLE check_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id     UUID REFERENCES standard_categories(id) NOT NULL,
    title           VARCHAR(500) NOT NULL,               -- 检查项标题
    description     TEXT,                                -- 详细说明
    check_method    TEXT,                                -- 检查方法
    legal_basis     TEXT,                                -- 法规条文依据
    standard_ref    VARCHAR(200),                        -- 标准编号引用
    result_type     VARCHAR(20) DEFAULT 'yes_no',
    -- 结果类型: yes_no / score / text / multi_choice
    result_options  JSONB,                               -- 选项（用于multi_choice）
    is_required     BOOLEAN DEFAULT TRUE,
    risk_level      VARCHAR(20) DEFAULT 'medium',
    -- 风险等级: high / medium / low
    sort_order      INTEGER DEFAULT 0,
    tags            TEXT[],
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 检查模板表 `inspection_templates`

```sql
CREATE TABLE inspection_templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(200) NOT NULL,
    code            VARCHAR(50) UNIQUE,
    description     TEXT,
    category        VARCHAR(100),    -- 模板分类（消防/食品/环保等）
    version         VARCHAR(20) DEFAULT '1.0',
    is_published    BOOLEAN DEFAULT FALSE,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 模板-条目关联表 `template_items`

```sql
CREATE TABLE template_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id     UUID REFERENCES inspection_templates(id) ON DELETE CASCADE,
    check_item_id   UUID REFERENCES check_items(id),
    sort_order      INTEGER DEFAULT 0,
    is_required     BOOLEAN DEFAULT TRUE,   -- 可覆盖条目本身的必填设置
    custom_title    VARCHAR(500),           -- 在该模板中自定义显示标题（可选）
    UNIQUE(template_id, check_item_id)
);
```

#### 检查任务表 `inspection_tasks`

```sql
CREATE TABLE inspection_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_no         VARCHAR(50) UNIQUE NOT NULL,         -- 任务编号（自动生成）
    title           VARCHAR(300) NOT NULL,
    template_id     UUID REFERENCES inspection_templates(id),
    assigned_to     UUID REFERENCES users(id),           -- 分配给哪位专家
    assigned_by     UUID REFERENCES users(id),
    target_name     VARCHAR(200),                        -- 被检查对象名称
    target_address  VARCHAR(500),                        -- 被检查地址
    target_contact  VARCHAR(100),                        -- 联系人
    target_phone    VARCHAR(20),
    scheduled_at    TIMESTAMP WITH TIME ZONE,            -- 计划时间
    started_at      TIMESTAMP WITH TIME ZONE,
    completed_at    TIMESTAMP WITH TIME ZONE,
    status          VARCHAR(20) DEFAULT 'pending',
    -- 状态: pending / in_progress / completed / cancelled
    remarks         TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 检查记录表 `inspection_records`（任务下每条检查条目的结果）

```sql
CREATE TABLE inspection_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID REFERENCES inspection_tasks(id) ON DELETE CASCADE,
    check_item_id   UUID REFERENCES check_items(id),
    result          VARCHAR(20),
    -- yes_no类型: compliant / non_compliant / not_applicable
    result_score    NUMERIC(5,2),                        -- 评分类型
    result_text     TEXT,                                -- 文字说明
    inspector_note  TEXT,                                -- 专家备注
    llm_suggestion  TEXT,                                -- LLM返回的监管建议（缓存）
    llm_basis       TEXT,                                -- LLM返回的法规依据（缓存）
    recorded_by     UUID REFERENCES users(id),
    recorded_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 媒体附件表 `media_files`

```sql
CREATE TABLE media_files (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID REFERENCES inspection_tasks(id),
    record_id       UUID REFERENCES inspection_records(id),  -- 可关联到具体条目
    file_type       VARCHAR(20) DEFAULT 'image',
    -- 类型: image / video / document
    original_name   VARCHAR(255),
    stored_name     VARCHAR(255) NOT NULL,               -- 服务器存储文件名
    file_path       VARCHAR(500) NOT NULL,
    file_size       BIGINT,
    mime_type       VARCHAR(100),
    thumbnail_path  VARCHAR(500),                        -- 缩略图路径
    lat             DOUBLE PRECISION,                    -- GPS坐标（拍照时获取）
    lng             DOUBLE PRECISION,
    uploaded_by     UUID REFERENCES users(id),
    uploaded_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 操作审计日志表 `audit_logs`

```sql
CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID REFERENCES users(id),
    username        VARCHAR(50),                         -- 冗余存储，防止用户被删后丢失
    action          VARCHAR(100) NOT NULL,
    -- 操作类型: login/logout/create_record/update_record/call_llm等
    resource_type   VARCHAR(50),                         -- 操作对象类型
    resource_id     VARCHAR(100),                        -- 操作对象ID
    detail          JSONB,                               -- 操作详情（如修改前后值）
    ip_address      VARCHAR(50),
    user_agent      TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 按时间分区（数据量大时优化查询）
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id, created_at DESC);
CREATE INDEX idx_audit_logs_action ON audit_logs(action, created_at DESC);
```

#### LLM 调用日志表 `llm_call_logs`

```sql
CREATE TABLE llm_call_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    task_id         UUID REFERENCES inspection_tasks(id),
    record_id       UUID REFERENCES inspection_records(id),
    call_type       VARCHAR(20) NOT NULL,                -- suggestion / basis
    prompt          TEXT NOT NULL,
    response        TEXT,
    model           VARCHAR(100),
    tokens_used     INTEGER,
    duration_ms     INTEGER,
    is_success      BOOLEAN DEFAULT TRUE,
    error_msg       TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

------

## 5. 后端开发规范

### 5.1 环境配置

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install fastapi uvicorn[standard] sqlalchemy asyncpg alembic \
            python-jose[cryptography] passlib[bcrypt] python-multipart \
            Pillow openai pydantic-settings python-dotenv redis
```

### 5.2 配置管理

```python
# backend/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 数据库
    PG_HOST: str = "117.72.77.52"
    PG_PORT: int = 5432
    PG_DB: str = "db_expert_opencode"
    PG_USER: str = "db_admin"
    PG_PASSWORD: str = "1234567890@sdtj"
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.PG_USER}:{self.PG_PASSWORD}@{self.PG_HOST}:{self.PG_PORT}/{self.PG_DB}"
    
    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8   # 8小时
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # LLM
    LLM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    LLM_MODEL: str = "deepseek-ai/deepseek-v3.2"
    LLM_API_KEY: str = "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"
    LLM_MAX_TOKENS: int = 8192
    LLM_TEMPERATURE: float = 1.0
    LLM_TOP_P: float = 0.95
    LLM_TIMEOUT: int = 30
    
    # 文件存储
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### 5.3 FastAPI 主入口

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routers import auth, users, templates, tasks, inspections, media, llm
from app.middleware.audit_middleware import AuditMiddleware

app = FastAPI(
    title="专家现场工作辅助系统 API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS（开发环境允许所有，生产环境限制域名）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境改为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 操作审计中间件
app.add_middleware(AuditMiddleware)

# 静态文件（上传的图片等）
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# 注册路由（所有路由统一加 /api 前缀）
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(users.router, prefix="/api/users", tags=["用户管理"])
app.include_router(templates.router, prefix="/api/templates", tags=["检查模板"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["检查任务"])
app.include_router(inspections.router, prefix="/api/inspections", tags=["检查记录"])
app.include_router(media.router, prefix="/api/media", tags=["文件上传"])
app.include_router(llm.router, prefix="/api/llm", tags=["LLM建议"])
```

### 5.4 审计日志中间件

所有写操作（POST/PUT/DELETE）需自动记录到 `audit_logs` 表：

```python
# backend/app/middleware/audit_middleware.py
# 记录内容：用户ID、操作类型、资源类型、IP、时间、请求摘要
# 注意：不记录密码等敏感字段
```

### 5.5 API 响应格式统一规范

所有接口返回统一格式：

```json
{
  "code": 200,
  "message": "success",
  "data": { ... },
  "timestamp": "2026-02-23T10:00:00Z"
}
```

错误响应：

```json
{
  "code": 401,
  "message": "未授权，请重新登录",
  "data": null,
  "timestamp": "2026-02-23T10:00:00Z"
}
```

------

## 6. 前端APP开发规范

### 6.1 核心页面设计

#### 任务列表页（首页）

- 显示当前用户被分配的所有任务
- 状态筛选（待开始/进行中/已完成）
- 任务卡片显示：任务编号、被检查对象、计划时间、进度百分比

#### 检查执行主页面

这是最核心的页面，需要重点设计：

```
┌─────────────────────────────────┐
│ ← 消防安全检查 #2024001         │
│ 检查对象：XX公司               │
│ 进度：12/30 条 (40%)           │
├─────────────────────────────────┤
│ 分类：A.建筑防火               │
│  ├─ A.1 防火间距               │
│  ├─ A.2 防火分区               │
│  └─ A.3 ...                    │
├─────────────────────────────────┤
│ 当前检查条目：                  │
│ A.1 防火间距是否满足规范要求    │
│                                │
│ [✓ 合规] [✗ 不合规] [— 不适用]  │
│                                │
│ 说明：___________________       │
│                                │
│ [📷 拍照]  [💡 建议]  [📖 依据] │
└─────────────────────────────────┘
```

#### LLM 建议弹窗

- 点击"建议"按钮 → 显示加载动画 → 展示 LLM 返回的监管建议
- 点击"依据"按钮 → 显示加载动画 → 展示该条目相关法规标准
- 支持结果复制到备注区

### 6.2 离线支持

移动端需支持弱网/断网场景：

- 任务数据在进入检查前全量缓存到本地 SQLite
- 检查结果先写本地，网络恢复后自动同步
- 照片上传失败时加入重试队列

### 6.3 拍照功能规范

```javascript
// 拍照后需要：
// 1. 压缩到 ≤ 2MB（保证上传速度）
// 2. 获取 GPS 坐标（如果用户授权）
// 3. 自动关联当前检查条目
// 4. 支持多张照片
```

------

## 7. Web管理平台开发规范

### 7.1 核心功能模块

#### 检查模板管理（最复杂的模块）

**标准条目库管理**

- 树形展示标准分类（支持多级，无限层级）
- 条目的增删改查
- 支持从 Excel 批量导入条目
- 每个条目可设置：标题、说明、检查方法、法规依据、风险等级

**模板配置器**

```
左侧：条目库（树形）      右侧：当前模板条目
┌────────────────┐       ┌───────────────────┐
│ 🏗️ 建筑防火    │       │ 模板名：消防安全检查│
│  ├─ 防火间距   │──拖拽→│                   │
│  ├─ 防火分区   │  或   │ 1. 防火间距 [必填] │
│  └─ 疏散通道   │ 点击  │ 2. 疏散通道 [必填] │
│ 🔌 电气安全    │  添加 │ 3. 灭火设施 [可选] │
│  ├─ ...        │       │ [上移][下移][删除] │
└────────────────┘       └───────────────────┘
```

**实现要点：**

- 使用 Ant Design `Tree` + `List` 组件
- 支持拖拽排序（`react-beautiful-dnd` 或 `dnd-kit`）
- 条目支持在模板中设为必填/可选（覆盖全局设置）
- 模板支持版本管理

#### 任务管理

- 创建检查任务：选择模板 → 选择负责专家 → 填写被检查对象信息 → 设定时间
- 任务进度追踪（实时看到专家完成了多少条）
- 任务状态流转管理

#### 数据分析仪表盘

- 本月检查任务统计（总数、完成率）
- 不合规条目 Top 10 统计（哪些问题最常出现）
- 专家工作量统计
- 时间趋势折线图
- 支持按时间范围、专家、任务类型筛选

#### 操作记录查看

- 所有用户操作的时间线（谁、何时、做了什么）
- 支持按用户、时间、操作类型筛选
- LLM 调用记录（查看 AI 建议的使用情况）

#### 检查报告管理

- 查看已完成任务的检查报告
- 支持导出 PDF/Word 格式

------

## 8. LLM集成规范

### 8.1 配置

```python
# backend/app/services/llm_service.py
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key="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",
    timeout=30.0,
)

LLM_MODEL = "deepseek-ai/deepseek-v3.2"
```

### 8.2 两种调用场景

#### 场景一：获取监管建议

**Prompt 模板：**

```python
SUGGESTION_PROMPT = """
你是一名专业的现场检查专家助手，请根据以下检查情况给出专业的监管建议。

【检查条目】：{check_item_title}
【检查结果】：{result}（合规/不合规/不适用）
【专家备注】：{inspector_note}
【检查方法说明】：{check_method}
【被检查对象类型】：{target_type}

请提供：
1. 针对此次检查结果的具体监管建议（如发现问题，给出整改要求和时限建议）
2. 后续跟踪监管要点
3. 如无问题，给出保持合规的注意事项

要求：内容专业、简洁、可操作，使用中文，不超过300字。
"""
```

#### 场景二：获取法规依据

**Prompt 模板：**

```python
BASIS_PROMPT = """
你是一名专业的法规标准专家，请为以下检查条目提供详细的法规标准依据。

【检查条目】：{check_item_title}
【条目说明】：{description}
【已知法规参考】：{legal_basis}

请提供：
1. 适用的具体法律法规名称和条款（如《消防法》第X条）
2. 相关技术标准和规范（如 GB 50016-2014 第X条）
3. 简要解释该依据的适用场景

要求：引用准确，使用中文，条目清晰，不超过400字。
"""
```

### 8.3 调用实现

```python
async def get_llm_suggestion(
    check_item: CheckItem,
    record: InspectionRecord,
    call_type: str  # "suggestion" 或 "basis"
) -> str:
    
    if call_type == "suggestion":
        prompt = SUGGESTION_PROMPT.format(
            check_item_title=check_item.title,
            result=record.result,
            inspector_note=record.inspector_note or "无",
            check_method=check_item.check_method or "未指定",
            target_type="通用",
        )
    else:
        prompt = BASIS_PROMPT.format(
            check_item_title=check_item.title,
            description=check_item.description or "无",
            legal_basis=check_item.legal_basis or "待查询",
        )
    
    try:
        response = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.7,   # 建议类任务用较低温度，保证稳定性
            top_p=0.95,
            stream=False,
        )
        return response.choices[0].message.content
    except Exception as e:
        # 记录错误，返回友好提示
        raise LLMServiceException(f"LLM 调用失败: {str(e)}")
```

### 8.4 缓存策略

- LLM 建议结果缓存到 `inspection_records.llm_suggestion` 字段
- 同一条目、同一结果的 LLM 建议，优先返回缓存（避免重复调用）
- 专家可手动点击"刷新建议"强制重新调用
- 所有调用记录写入 `llm_call_logs` 表，用于成本分析

### 8.5 错误处理

- 超时（30秒）返回提示："AI建议获取超时，请稍后重试"
- API 限流时，使用指数退避重试（最多3次）
- 网络错误时提示用户，不影响检查记录的保存

------

## 9. 用户权限与安全

### 9.1 权限矩阵

| 功能           | 超级管理员 | 普通管理员 | 现场专家 | 只读审计员 |
| -------------- | ---------- | ---------- | -------- | ---------- |
| 用户管理       | ✅          | ❌          | ❌        | ❌          |
| 条目库管理     | ✅          | ✅          | ❌        | ❌          |
| 模板管理       | ✅          | ✅          | ❌        | ❌          |
| 创建任务       | ✅          | ✅          | ❌        | ❌          |
| 执行检查       | ❌          | ❌          | ✅        | ❌          |
| 查看自己的记录 | ✅          | ✅          | ✅        | ❌          |
| 查看所有记录   | ✅          | ✅          | ❌        | ✅          |
| 数据分析       | ✅          | ✅          | ❌        | ✅          |
| 系统配置       | ✅          | ❌          | ❌        | ❌          |

### 9.2 认证方案

```
登录流程：
1. 用户提交 username + password
2. 验证通过 → 返回 access_token（8小时有效）+ refresh_token（30天有效）
3. 请求头：Authorization: Bearer <access_token>
4. access_token 过期 → 用 refresh_token 换取新 access_token
5. refresh_token 过期 → 重新登录

Token 吊销：
- 退出登录时将 refresh_token 加入 Redis 黑名单
- 修改密码后使该用户所有 token 失效
```

### 9.3 数据安全措施

- 密码使用 **bcrypt** 哈希存储（cost factor = 12）
- 数据库连接使用 SSL（如服务器支持）
- 上传文件做格式白名单校验（仅允许 jpg/png/heic/pdf 等）
- 文件名使用 UUID 重命名，不保留原始文件名路径
- 敏感配置（DB密码、LLM API Key）通过环境变量注入，不硬编码在代码中
- 接口访问频率限制（特别是 LLM 接口，防止滥用）

### 9.4 数据备份策略

```bash
# PostgreSQL 定时备份脚本（建议配置 cron）
# 每天凌晨2点全量备份，保留30天
0 2 * * * pg_dump -h 117.72.77.52 -U db_admin db_expert_opencode | gzip > /backup/efis_$(date +%Y%m%d).sql.gz

# 上传文件目录同步备份
# 建议每天同步到另一台服务器或对象存储
```

------

## 10. 部署与运行环境

### 10.1 目录结构（生产环境）

```
/opt/efis/
├── .venv/                  # Python 虚拟环境（在此目录内）
├── backend/
├── web-admin/dist/         # 前端构建产物
├── uploads/                # 用户上传文件
├── logs/                   # 应用日志
└── scripts/
    ├── start.sh            # 启动脚本
    └── backup.sh           # 备份脚本
```

### 10.2 启动命令

```bash
# 激活虚拟环境
source /opt/efis/.venv/bin/activate

# 启动后端（生产环境）
cd /opt/efis/backend
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 127.0.0.1:8000 \
  --timeout 60 \
  --access-logfile ../logs/access.log \
  --error-logfile ../logs/error.log \
  --daemon
```

### 10.3 Nginx 配置

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Web 管理平台（静态文件）
    location / {
        root /opt/efis/web-admin/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 60s;    # LLM 调用可能较慢
    }

    # 上传文件
    location /uploads/ {
        alias /opt/efis/uploads/;
        expires 7d;
        add_header Cache-Control "public";
    }
    
    client_max_body_size 20M;   # 支持大文件上传
}
```

### 10.4 数据库初始化

```bash
# 执行 Alembic 迁移（首次部署）
cd /opt/efis/backend
source ../.venv/bin/activate
alembic upgrade head

# 创建初始超级管理员账户
python scripts/create_superadmin.py
```

------

## 11. 开发阶段规划

### Phase 1（基础框架）— 预计 3-4 天

- [ ] 后端项目初始化（FastAPI + SQLAlchemy + Alembic）
- [ ] 数据库建表（所有核心表）
- [ ] 用户认证模块（注册/登录/JWT）
- [ ] 基本权限控制中间件
- [ ] Web管理平台框架搭建（登录页 + 基础布局）

### Phase 2（核心功能）— 预计 5-7 天

- [ ] 检查条目库管理（CRUD + 树形分类）
- [ ] 检查模板配置器（条目选择 + 排序）
- [ ] 检查任务管理（创建/分配/状态管理）
- [ ] 移动端APP框架 + 任务列表页
- [ ] 检查执行主页面（表单录入 + 结果记录）

### Phase 3（LLM集成 + 媒体）— 预计 3-4 天

- [ ] LLM 服务封装（建议 + 依据两种调用）
- [ ] APP端 LLM 调用（弹窗展示 + 加载状态）
- [ ] 照片拍摄上传功能
- [ ] 文件管理后端接口

### Phase 4（管理分析）— 预计 3-4 天

- [ ] 数据分析仪表盘
- [ ] 操作审计日志查看
- [ ] 检查报告生成（PDF导出）
- [ ] 用户管理（后台）

### Phase 5（优化上线）— 预计 2-3 天

- [ ] 离线缓存优化（移动端）
- [ ] 性能优化（接口分页、图片压缩）
- [ ] 安全加固（频率限制、文件校验）
- [ ] 部署配置（Nginx + Gunicorn）
- [ ] 功能测试 + Bug 修复

------

## 12. API接口规范

### 12.1 认证接口

```
POST   /api/auth/login          # 登录，返回 token
POST   /api/auth/logout         # 退出
POST   /api/auth/refresh        # 刷新 token
GET    /api/auth/me             # 获取当前用户信息
PUT    /api/auth/me/password    # 修改密码
```

### 12.2 模板管理接口

```
# 标准分类
GET    /api/templates/categories          # 获取分类树
POST   /api/templates/categories          # 创建分类
PUT    /api/templates/categories/{id}     # 更新分类
DELETE /api/templates/categories/{id}     # 删除分类

# 检查条目
GET    /api/templates/items               # 条目列表（支持分类筛选）
POST   /api/templates/items               # 创建条目
PUT    /api/templates/items/{id}          # 更新条目
DELETE /api/templates/items/{id}          # 删除条目
POST   /api/templates/items/import        # 批量导入（Excel）

# 检查模板
GET    /api/templates/                    # 模板列表
POST   /api/templates/                    # 创建模板
GET    /api/templates/{id}                # 获取模板详情（含所有条目）
PUT    /api/templates/{id}                # 更新模板信息
DELETE /api/templates/{id}                # 删除模板
POST   /api/templates/{id}/publish        # 发布模板
POST   /api/templates/{id}/items          # 添加条目到模板
DELETE /api/templates/{id}/items/{item_id} # 从模板移除条目
PUT    /api/templates/{id}/items/sort     # 重排序条目
```

### 12.3 任务管理接口

```
GET    /api/tasks/                        # 任务列表（管理员看全部，专家看自己的）
POST   /api/tasks/                        # 创建任务
GET    /api/tasks/{id}                    # 任务详情
PUT    /api/tasks/{id}                    # 更新任务
POST   /api/tasks/{id}/start             # 开始任务
POST   /api/tasks/{id}/complete          # 完成任务
```

### 12.4 检查记录接口

```
GET    /api/inspections/{task_id}/records          # 获取任务下所有检查记录
POST   /api/inspections/{task_id}/records          # 创建/更新检查记录
PUT    /api/inspections/records/{record_id}        # 更新单条记录
GET    /api/inspections/{task_id}/summary          # 检查汇总（合规率等）
```

### 12.5 LLM接口

```
POST   /api/llm/suggestion      # 获取监管建议
POST   /api/llm/basis           # 获取法规依据

# 请求体：
{
  "task_id": "uuid",
  "record_id": "uuid",
  "check_item_id": "uuid",
  "use_cache": true   # 是否使用缓存结果
}
```

### 12.6 文件接口

```
POST   /api/media/upload        # 上传文件（multipart/form-data）
DELETE /api/media/{id}          # 删除文件
GET    /api/media/task/{task_id} # 获取任务下所有媒体文件
```

### 12.7 管理分析接口

```
GET    /api/analytics/dashboard         # 仪表盘数据
GET    /api/analytics/tasks             # 任务统计
GET    /api/analytics/non-compliance    # 不合规条目统计
GET    /api/analytics/experts           # 专家工作量统计
GET    /api/audit-logs/                 # 操作审计日志（分页）
GET    /api/llm/logs/                   # LLM调用记录（分页）
```

------

## 13. 附录：配置信息

### 13.1 数据库连接

```
Host:     117.72.77.52
Port:     5432
Database: db_expert_opencode
User:     db_admin
Password: 1234567890@sdtj
```

### 13.2 LLM 服务

```
Base URL:    https://integrate.api.nvidia.com/v1
Model:       deepseek-ai/deepseek-v3.2
API Key:     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
Max Tokens:  8192
Temperature: 1.0
Top P:       0.95
Timeout:     30s
```

**备用模型（在 config 中可切换）：**

```
deepseek-ai/deepseek-v3.1
qwen/qwen3-coder-480b-a35b-instruct
minimaxai/minimax-m2.1
moonshotai/kimi-k2.5
openai/gpt-oss-120b
z-ai/glm4.7
```

### 13.3 环境变量文件模板（`.env`）

```env
# 数据库
PG_HOST=117.72.77.52
PG_PORT=5432
PG_DB=db_expert_opencode
PG_USER=db_admin
PG_PASSWORD=1234567890@sdtj

# JWT（生产环境必须修改为随机强密钥）
SECRET_KEY=change-this-to-a-random-secret-key-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=480
REFRESH_TOKEN_EXPIRE_DAYS=30

# LLM
LLM_BASE_URL=https://integrate.api.nvidia.com/v1
LLM_MODEL=deepseek-ai/deepseek-v3.2
LLM_API_KEY=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

# 文件存储
UPLOAD_DIR=./uploads

# 运行模式
DEBUG=false
```

### 13.4 AI Agent 开发注意事项

1. **每次生成代码后**，确保与此设计文档中的表结构和接口规范一致
2. **数据库操作**统一使用 SQLAlchemy 异步 ORM，不直接拼接 SQL（防注入）
3. **LLM 调用**必须有超时控制和错误处理，不能因 AI 服务异常影响检查记录保存
4. **权限检查**每个接口都需要通过 Depends 注入认证和权限验证
5. **审计日志**写入操作失败不能影响主业务，用 try/except 保护
6. **文件上传**必须校验 MIME 类型和文件大小，重命名存储
7. **移动端**优先考虑弱网场景，所有写操作做本地缓存兜底

------

*文档结束 — 本指南应作为 AI Agent 开发的权威参考，如有变更请同步更新*