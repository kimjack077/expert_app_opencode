

# 专家辅助检查工作系统 — MVP 开发指南

> **版本**: v1.0  
> **日期**: 2025-01  
> **目标**: 指导 AI Agent 完成完整的 MVP 系统开发  

---

## 一、项目概述

### 1.1 系统定位

本系统是一个**通用型专家现场检查辅助工作平台**，支持食品安全检查、安全生产检查、ISO认证审核等多行业场景。核心价值是**灵活的检查模板引擎 + AI 辅助生成检查结论**。

### 1.2 产品形态

| 端 | 说明 | 技术方案 |
|---|---|---|
| **Web 管理端** | 后台管理：模板配置、企业管理、检查记录查看、用户管理 | Flask + Jinja2 服务端渲染（前后端不分离） |
| **H5 移动端** | 专家现场使用：选企业、选模板、执行检查、AI辅助、拍照上传 | Flask 提供移动端页面 + REST API，移动端优化的 HTML5 页面 |

### 1.3 核心功能清单

```
1. 用户与权限管理
2. 行业分类管理
3. 企业信息管理
4. 检查模板管理（核心，无限层级树形结构）
5. 现场检查执行（H5端）
6. 检查记录管理与查看
7. AI 辅助生成检查结论
8. 附件管理（拍照/上传）
```

---

## 二、技术栈

### 2.1 后端

| 组件 | 技术选型 | 版本要求 | 说明 |
|---|---|---|---|
| 语言 | Python | ≥ 3.10 | |
| Web 框架 | FastAPI | ≥ 0.100 | 高性能异步框架，自动生成API文档 |
| ORM | SQLAlchemy (async) | ≥ 2.0 | 支持异步操作 |
| 数据库迁移 | Alembic | | |
| 数据库 | PostgreSQL | 远程，已提供 | |
| 数据验证 | Pydantic | ≥ 2.0 | 数据模型验证，FastAPI内置支持 |
| 用户认证 | JWT (python-jose) | | 统一使用JWT认证 |
| 文件上传 | FastAPI UploadFile + Pillow | | 图片压缩处理 |
| AI 调用 | openai (Python SDK) | | OpenAI 兼容接口 |
| 密码加密 | passlib + bcrypt | | |

### 2.2 前端

| 端 | 技术栈 | 说明 |
|---|---|---|
| Web 管理端 | React 18 + TypeScript + Vite + Ant Design | 现代化SPA，组件化开发 |
| H5 移动端 | Vue 3 + Vant 4 + Vite + TypeScript | 移动优先，组件化交互 |

### 2.3 基础设施

```
数据库:
  PG_HOST: 62.234.0.182
  PG_PORT: 5432
  PG_DB: expert_new_mvp1
  PG_USER: expert_new_mvp1
  PG_PASSWORD: 1234567890@sdtj

AI 大模型（OpenAI 兼容）:
  API_BASE_URL: <待配置>
  API_KEY: <待配置>
  MODEL_NAME: <待配置>

文件存储: 本地文件系统 (./uploads/)
```

---

## 三、项目目录结构

```
expert_app_opencode/
│
├── backend/                        # 后端服务
│   ├── main.py                     # FastAPI 应用入口
│   ├── requirements.txt            # Python 依赖
│   ├── alembic.ini                 # Alembic 配置
│   ├── .env                        # 环境变量（不入版本控制）
│   │
│   ├── alembic/                    # 数据库迁移
│   │   ├── env.py
│   │   └── versions/               # 迁移脚本
│   │
│   └── app/
│       ├── __init__.py
│       ├── main.py                 # FastAPI 应用创建
│       ├── config.py               # 配置类
│       ├── database.py             # 数据库连接
│       │
│       ├── models/                 # SQLAlchemy 数据模型
│       │   ├── __init__.py
│       │   ├── base.py             # 基础模型类
│       │   ├── user.py             # 用户 & 组织模型
│       │   ├── template.py         # 检查模板 & 模板节点模型
│       │   ├── enterprise.py       # 企业模型（含资质、设备、人员等）
│       │   ├── task.py             # 检查任务模型
│       │   ├── record.py           # 检查记录模型
│       │   ├── media.py            # 媒体文件模型
│       │   ├── knowledge.py        # 知识库模型
│       │   └── audit.py            # 审计日志模型
│       │
│       ├── schemas/                # Pydantic 数据模式
│       │   ├── __init__.py
│       │   ├── common.py           # 通用模式
│       │   ├── user.py
│       │   ├── template.py
│       │   ├── enterprise.py
│       │   ├── task.py
│       │   └── record.py
│       │
│       ├── routers/                # FastAPI 路由
│       │   ├── __init__.py
│       │   ├── auth.py             # 认证接口
│       │   ├── templates.py        # 模板管理接口
│       │   ├── enterprises.py      # 企业管理接口
│       │   ├── tasks.py            # 检查任务接口
│       │   ├── records.py          # 检查记录接口
│       │   ├── media.py            # 文件上传接口
│       │   ├── llm.py              # AI/LLM 接口
│       │   ├── ai_extract.py       # AI提取接口
│       │   ├── knowledge.py        # 知识库接口
│       │   └── analytics.py        # 数据分析接口
│       │
│       ├── services/               # 业务逻辑层
│       │   ├── __init__.py
│       │   ├── services.py         # 通用服务
│       │   ├── llm_service.py      # LLM调用服务
│       │   └── ai_extract_service.py # AI提取服务
│       │
│       ├── middleware/             # 中间件
│       │   ├── __init__.py
│       │   └── audit_middleware.py # 审计中间件
│       │
│       └── utils/                  # 工具函数
│           ├── __init__.py
│           ├── security.py         # 安全相关（密码加密等）
│           ├── file_handler.py     # 文件处理
│           └── document_parser.py  # 文档解析
│
├── web-admin/                      # Web 管理端 (React + TypeScript)
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   │
│   └── src/
│       ├── main.tsx                # 应用入口
│       ├── App.tsx                 # 根组件
│       ├── index.css               # 全局样式
│       │
│       ├── components/             # 公共组件
│       │   └── MainLayout.tsx      # 主布局组件
│       │
│       ├── pages/                  # 页面组件
│       │   ├── Login/              # 登录页
│       │   ├── Dashboard/          # 仪表盘
│       │   ├── Templates/          # 模板管理
│       │   │   ├── index.tsx       # 模板列表
│       │   │   ├── TemplateEditorV2.tsx  # 新版模板编辑器
│       │   │   └── AiExtractModal.tsx    # AI提取弹窗
│       │   ├── Enterprises/        # 企业管理
│       │   ├── Tasks/              # 任务管理
│       │   ├── Records/            # 检查记录
│       │   ├── Knowledge/          # 知识库
│       │   ├── Analytics/          # 数据分析
│       │   └── Inspection/         # 检查执行
│       │
│       ├── services/               # API 服务
│       │   └── api.ts
│       │
│       └── stores/                 # 状态管理
│           ├── app.ts
│           └── auth.ts
│
├── h5-app/                         # H5 移动端 (Vue 3 + TypeScript)
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   │
│   └── src/
│       ├── main.ts                 # 应用入口
│       ├── App.vue                 # 根组件
│       │
│       ├── api/                    # API 服务
│       │   ├── request.ts          # Axios 封装
│       │   ├── auth.ts
│       │   ├── tasks.ts
│       │   ├── records.ts
│       │   └── media.ts
│       │
│       ├── components/             # 公共组件
│       │   └── TreeItem.vue
│       │
│       ├── views/                  # 页面组件
│       │   ├── Login.vue           # 登录页
│       │   ├── Home.vue            # 首页
│       │   ├── Tasks.vue           # 任务列表
│       │   ├── TaskDetail.vue      # 任务详情
│       │   ├── SelectEnterprise.vue # 选择企业
│       │   ├── SelectTemplate.vue  # 选择模板
│       │   ├── InspectionExecution.vue # 检查执行
│       │   ├── InspectItem.vue     # 检查项详情
│       │   ├── Records.vue         # 检查记录列表
│       │   ├── RecordDetail.vue    # 记录详情
│       │   ├── Profile.vue         # 个人中心
│       │   ├── About.vue           # 关于
│       │   ├── Settings.vue        # 设置
│       │   └── Statistics.vue      # 统计
│       │
│       └── styles/                 # 样式
│           └── global.css
│
└── uploads/                        # 上传文件存储目录
    └── attachments/
```

---

## 四、数据库设计

### 4.1 ER 关系图（文字描述）

```
[industries] 1──N [industries]          (自引用，行业分类树)
[industries] 1──N [check_templates]     (模板属于某行业)
[industries] 1──N [users]              (用户属于某行业)
[industries] 1──N [enterprises]        (企业属于某行业)

[check_templates] 1──N [template_nodes] (模板包含多个节点)
[template_nodes] 1──N [template_nodes]  (自引用，无限层级)

[users] 1──N [inspections]             (专家执行检查)
[enterprises] 1──N [inspections]       (企业被检查)
[check_templates] 1──N [inspections]   (使用某模板检查)

[inspections] 1──N [inspection_results] (检查包含多个结果)
[template_nodes] 1──N [inspection_results] (结果对应模板节点)
[inspection_results] 1──N [attachments] (结果可有附件)
```

### 4.2 详细建表 SQL

> **注意**: 实际开发中使用 Flask-Migrate 通过 ORM 模型自动生成迁移脚本，以下 SQL 仅作为数据库设计参考。

```sql
-- ============================================================
-- 1. 行业分类表（支持树形结构）
-- ============================================================
CREATE TABLE industries (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,              -- 分类名称，如"食品安全"、"安全生产"
    code VARCHAR(50) UNIQUE,                 -- 分类编码
    description TEXT,                        -- 分类描述
    parent_id INTEGER REFERENCES industries(id) ON DELETE SET NULL,  -- 父分类ID
    sort_order INTEGER DEFAULT 0,            -- 排序
    icon VARCHAR(100),                       -- 图标（可选）
    is_active BOOLEAN DEFAULT TRUE,          -- 是否启用
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 初始数据示例
-- INSERT INTO industries (name, code) VALUES ('食品安全', 'food_safety');
-- INSERT INTO industries (name, code) VALUES ('安全生产', 'work_safety');
-- INSERT INTO industries (name, code) VALUES ('ISO认证审核', 'iso_audit');

-- ============================================================
-- 2. 用户表
-- ============================================================
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,    -- 登录用户名
    password_hash VARCHAR(256) NOT NULL,     -- 密码哈希
    real_name VARCHAR(50),                   -- 真实姓名
    phone VARCHAR(20),                       -- 手机号
    email VARCHAR(100),                      -- 邮箱
    avatar VARCHAR(500),                     -- 头像路径
    role VARCHAR(20) NOT NULL DEFAULT 'expert',  -- 角色: admin(管理员), manager(管理者), expert(专家)
    industry_id INTEGER REFERENCES industries(id) ON DELETE SET NULL,  -- 所属行业
    organization VARCHAR(200),               -- 所属机构
    title VARCHAR(100),                      -- 职称/头衔
    is_active BOOLEAN DEFAULT TRUE,          -- 是否启用
    last_login_at TIMESTAMP,                 -- 最后登录时间
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- 3. 企业信息表
-- ============================================================
CREATE TABLE enterprises (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,              -- 企业名称
    unified_code VARCHAR(50),                -- 统一社会信用代码
    industry_id INTEGER REFERENCES industries(id) ON DELETE SET NULL,  -- 所属行业
    province VARCHAR(50),                    -- 省份
    city VARCHAR(50),                        -- 城市
    district VARCHAR(50),                    -- 区县
    address TEXT,                            -- 详细地址
    contact_person VARCHAR(50),              -- 联系人
    contact_phone VARCHAR(20),               -- 联系电话
    contact_email VARCHAR(100),              -- 联系邮箱
    enterprise_type VARCHAR(50),             -- 企业类型
    scale VARCHAR(50),                       -- 企业规模
    description TEXT,                        -- 企业简介
    is_active BOOLEAN DEFAULT TRUE,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- 4. 检查模板表
-- ============================================================
CREATE TABLE check_templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,              -- 模板名称
    code VARCHAR(50),                        -- 模板编码
    industry_id INTEGER REFERENCES industries(id) ON DELETE SET NULL,  -- 所属行业分类
    description TEXT,                        -- 模板描述/使用说明
    version VARCHAR(20) DEFAULT '1.0',       -- 版本号
    status VARCHAR(20) DEFAULT 'draft',      -- 状态: draft(草稿), published(已发布), archived(已归档)
    scoring_mode VARCHAR(20) DEFAULT 'none', -- 计分模式: none(不计分), sum(累加), average(平均), weighted(加权)
    total_max_score DECIMAL(10,2),           -- 满分值（如果计分）
    pass_score DECIMAL(10,2),               -- 及格分数（如果计分）
    is_template BOOLEAN DEFAULT TRUE,        -- 是否为模板（区别于模板实例）
    created_by INTEGER REFERENCES users(id),
    published_at TIMESTAMP,                  -- 发布时间
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_templates_industry ON check_templates(industry_id);
CREATE INDEX idx_templates_status ON check_templates(status);

-- ============================================================
-- 5. 模板节点表（核心！树形结构，支持无限层级）
-- ============================================================
CREATE TABLE template_nodes (
    id SERIAL PRIMARY KEY,
    template_id INTEGER NOT NULL REFERENCES check_templates(id) ON DELETE CASCADE,
    parent_id INTEGER REFERENCES template_nodes(id) ON DELETE CASCADE,  -- 父节点，NULL表示根节点
    
    -- 基本信息
    name VARCHAR(500) NOT NULL,              -- 节点名称（分类名或检查项名称）
    description TEXT,                        -- 节点描述/说明
    node_type VARCHAR(20) NOT NULL,          -- 节点类型: 'category'(分类节点), 'item'(检查项)
    sort_order INTEGER DEFAULT 0,            -- 同级排序序号
    node_code VARCHAR(50),                   -- 节点编号（如 1.1, 1.1.1）
    
    -- ==========================================
    -- 以下字段仅对 node_type = 'item' 有效
    -- ==========================================
    
    -- 检查方式
    check_type VARCHAR(20),                  -- 'score'(打分), 'radio'(单选判定), 'numeric'(数值), 'text'(文本描述), 'multi_check'(多选)
    is_required BOOLEAN DEFAULT FALSE,       -- 是否必填项
    
    -- ---- 打分类型 (check_type='score') 配置 ----
    max_score DECIMAL(10,2),                 -- 该项最高分
    min_score DECIMAL(10,2) DEFAULT 0,       -- 该项最低分
    score_step DECIMAL(10,2) DEFAULT 1,      -- 打分步长（如 0.5, 1, 5）
    default_score DECIMAL(10,2),             -- 默认分数
    score_weight DECIMAL(5,2) DEFAULT 1.0,   -- 权重（用于加权计分）
    
    -- ---- 单选判定 (check_type='radio') 配置 ----
    -- 示例: [{"label":"合格","value":"pass","color":"green"},{"label":"不合格","value":"fail","color":"red"}]
    -- 示例: [{"label":"符合","value":"conform"},{"label":"不符合","value":"non_conform"},{"label":"不适用","value":"na"}]
    radio_options JSONB,                     
    default_radio VARCHAR(50),               -- 默认选项值
    
    -- ---- 数值类型 (check_type='numeric') 配置 ----
    numeric_min DECIMAL(15,4),               -- 数值下限
    numeric_max DECIMAL(15,4),               -- 数值上限
    numeric_unit VARCHAR(30),                -- 单位（如 ℃, mg/L, %）
    numeric_precision INTEGER DEFAULT 2,     -- 小数精度
    
    -- ---- 多选 (check_type='multi_check') 配置 ----
    -- 示例: [{"label":"文件齐全","value":"doc_ok"},{"label":"现场整洁","value":"site_clean"},...]
    multi_options JSONB,
    
    -- ---- 文本描述 (check_type='text') 配置 ----
    text_placeholder VARCHAR(500),           -- 输入提示文字
    text_min_length INTEGER DEFAULT 0,       -- 最少字数
    
    -- ==========================================
    -- 附件配置
    -- ==========================================
    allow_attachment BOOLEAN DEFAULT FALSE,   -- 是否允许附件
    attachment_required BOOLEAN DEFAULT FALSE, -- 附件是否必须
    max_attachments INTEGER DEFAULT 5,        -- 最大附件数
    allowed_file_types VARCHAR(200) DEFAULT 'image/*,.pdf,.doc,.docx,.xls,.xlsx',  -- 允许的文件类型
    
    -- ==========================================
    -- 知识库 / 专家支撑信息
    -- ==========================================
    legal_basis TEXT,                         -- 法律依据（支持多条，每条换行）
    standard_basis TEXT,                      -- 标准依据（如 GB xxxxx-2020 第x条）
    regulation_basis TEXT,                    -- 规章/规范依据
    key_points TEXT,                          -- 现场检查要点/重点提示
    common_problems TEXT,                     -- 常见问题描述
    reference_docs JSONB,                    -- 参考文档: [{"title":"xxx","url":"xxx"}]
    
    -- ==========================================
    -- AI 辅助配置
    -- ==========================================
    ai_enabled BOOLEAN DEFAULT TRUE,         -- 是否启用AI辅助
    ai_prompt_template TEXT,                 -- 自定义AI提示词模板（可覆盖默认）
    
    -- 元数据
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_nodes_template ON template_nodes(template_id);
CREATE INDEX idx_nodes_parent ON template_nodes(parent_id);
CREATE INDEX idx_nodes_type ON template_nodes(node_type);

-- ============================================================
-- 6. 检查任务表（检查记录主表）
-- ============================================================
CREATE TABLE inspections (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE,                 -- 检查编号（自动生成，如 INS-20250101-001）
    
    enterprise_id INTEGER NOT NULL REFERENCES enterprises(id),
    template_id INTEGER NOT NULL REFERENCES check_templates(id),
    inspector_id INTEGER NOT NULL REFERENCES users(id),  -- 执行检查的专家
    
    -- 检查信息
    inspection_date DATE NOT NULL DEFAULT CURRENT_DATE,   -- 检查日期
    inspection_type VARCHAR(50),             -- 检查类型（例如：日常检查、专项检查、复查等）
    
    -- 状态与进度
    status VARCHAR(20) DEFAULT 'in_progress',-- 'in_progress'(进行中), 'completed'(已完成), 'reviewed'(已审核)
    progress INTEGER DEFAULT 0,              -- 完成进度百分比
    total_items INTEGER DEFAULT 0,           -- 总检查项数
    completed_items INTEGER DEFAULT 0,       -- 已完成检查项数
    
    -- 结果汇总
    total_score DECIMAL(10,2),               -- 总得分
    max_possible_score DECIMAL(10,2),        -- 总满分
    pass_count INTEGER DEFAULT 0,            -- 合格项数
    fail_count INTEGER DEFAULT 0,            -- 不合格项数
    na_count INTEGER DEFAULT 0,              -- 不适用项数
    
    -- 总体结论
    overall_result VARCHAR(20),              -- 'pass'(通过), 'fail'(不通过), 'conditional'(有条件通过)
    overall_conclusion TEXT,                 -- 总体结论描述
    inspector_signature TEXT,                -- 检查人签名（可存 base64）
    enterprise_signature TEXT,               -- 企业方签名
    
    remarks TEXT,                            -- 备注
    
    -- 时间记录
    started_at TIMESTAMP,                    -- 开始检查时间
    completed_at TIMESTAMP,                  -- 完成检查时间
    reviewed_at TIMESTAMP,                   -- 审核时间
    reviewed_by INTEGER REFERENCES users(id),-- 审核人
    
    -- GPS 定位（可选）
    latitude DECIMAL(10,7),
    longitude DECIMAL(10,7),
    location_address VARCHAR(500),
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_inspections_enterprise ON inspections(enterprise_id);
CREATE INDEX idx_inspections_inspector ON inspections(inspector_id);
CREATE INDEX idx_inspections_status ON inspections(status);
CREATE INDEX idx_inspections_date ON inspections(inspection_date);

-- ============================================================
-- 7. 检查结果明细表
-- ============================================================
CREATE TABLE inspection_results (
    id SERIAL PRIMARY KEY,
    inspection_id INTEGER NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
    node_id INTEGER NOT NULL REFERENCES template_nodes(id),  -- 对应的模板节点
    
    -- 冗余存储（方便查询，从模板节点复制）
    node_name VARCHAR(500),                  -- 检查项名称
    check_type VARCHAR(20),                  -- 检查方式
    
    -- ==========================================
    -- 检查结果值（根据 check_type 使用对应字段）
    -- ==========================================
    score_value DECIMAL(10,2),               -- 打分结果
    radio_value VARCHAR(50),                 -- 单选判定结果
    numeric_value DECIMAL(15,4),             -- 数值结果
    text_value TEXT,                         -- 文本描述结果
    multi_value JSONB,                       -- 多选结果 ["doc_ok","site_clean"]
    
    -- 问题记录
    has_problem BOOLEAN DEFAULT FALSE,       -- 是否发现问题
    problem_description TEXT,                -- 问题描述
    severity VARCHAR(20),                    -- 问题严重程度: minor(一般), major(严重), critical(严重)
    rectification_suggestion TEXT,           -- 整改建议
    
    -- AI 辅助记录
    ai_generated BOOLEAN DEFAULT FALSE,      -- 结论是否由AI生成
    ai_suggestion TEXT,                      -- AI 生成的建议/结论
    ai_reference TEXT,                       -- AI 引用的标准/依据
    ai_used_at TIMESTAMP,                    -- AI 调用时间
    
    -- 状态
    is_completed BOOLEAN DEFAULT FALSE,      -- 是否已完成该项检查
    is_na BOOLEAN DEFAULT FALSE,             -- 是否不适用
    
    remarks TEXT,                            -- 备注
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_results_inspection ON inspection_results(inspection_id);
CREATE INDEX idx_results_node ON inspection_results(node_id);

-- ============================================================
-- 8. 附件表
-- ============================================================
CREATE TABLE attachments (
    id SERIAL PRIMARY KEY,
    inspection_result_id INTEGER REFERENCES inspection_results(id) ON DELETE CASCADE,
    
    file_name VARCHAR(500) NOT NULL,         -- 原始文件名
    file_path VARCHAR(500) NOT NULL,         -- 存储路径
    file_type VARCHAR(20) NOT NULL,          -- 'image'(图片), 'document'(文档)
    file_size INTEGER,                       -- 文件大小(字节)
    mime_type VARCHAR(100),                  -- MIME类型
    
    -- 图片特有
    thumbnail_path VARCHAR(500),             -- 缩略图路径
    image_width INTEGER,                     -- 图片宽度
    image_height INTEGER,                    -- 图片高度
    
    -- 来源
    source VARCHAR(20) DEFAULT 'upload',     -- 'upload'(上传), 'camera'(拍照)
    
    description VARCHAR(500),                -- 附件描述/说明
    sort_order INTEGER DEFAULT 0,
    
    uploaded_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_attachments_result ON attachments(inspection_result_id);
```

### 4.3 数据模型关系总结

```
industries（行业分类，自引用树）
    ├── users（用户属于行业）
    ├── enterprises（企业属于行业）
    └── check_templates（模板属于行业）
            └── template_nodes（模板节点，自引用树，无限层级）
                    ├── node_type = 'category' → 分类节点（有子节点）
                    └── node_type = 'item' → 检查项（叶子节点，含检查配置）

inspections（检查任务）
    ├── → enterprise（被检查企业）
    ├── → check_template（使用的模板）
    ├── → user（执行的专家）
    └── inspection_results（检查结果明细）
            ├── → template_node（对应的模板节点）
            └── attachments（附件/照片）
```

---

## 五、ORM 模型定义

### 5.1 `app/models/user.py`

```python
from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    real_name = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    avatar = db.Column(db.String(500))
    role = db.Column(db.String(20), nullable=False, default='expert')
    industry_id = db.Column(db.Integer, db.ForeignKey('industries.id'))
    organization = db.Column(db.String(200))
    title = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    last_login_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 关系
    industry = db.relationship('Industry', backref='users')
    inspections = db.relationship('Inspection', backref='inspector', foreign_keys='Inspection.inspector_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'real_name': self.real_name,
            'phone': self.phone,
            'role': self.role,
            'industry_id': self.industry_id,
            'organization': self.organization,
            'is_active': self.is_active,
        }
```

### 5.2 `app/models/industry.py`

```python
from app.extensions import db
from datetime import datetime


class Industry(db.Model):
    __tablename__ = 'industries'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(50), unique=True)
    description = db.Column(db.Text)
    parent_id = db.Column(db.Integer, db.ForeignKey('industries.id'))
    sort_order = db.Column(db.Integer, default=0)
    icon = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 自引用关系
    children = db.relationship('Industry', backref=db.backref('parent', remote_side=[id]),
                               order_by='Industry.sort_order')
    
    # 关联
    templates = db.relationship('CheckTemplate', backref='industry')
    enterprises = db.relationship('Enterprise', backref='industry')

    def to_dict(self, include_children=False):
        data = {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'description': self.description,
            'parent_id': self.parent_id,
            'sort_order': self.sort_order,
            'is_active': self.is_active,
        }
        if include_children:
            data['children'] = [c.to_dict(include_children=True) for c in self.children]
        return data
```

### 5.3 `app/models/template.py`

```python
from app.extensions import db
from datetime import datetime


class CheckTemplate(db.Model):
    __tablename__ = 'check_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(50))
    industry_id = db.Column(db.Integer, db.ForeignKey('industries.id'))
    description = db.Column(db.Text)
    version = db.Column(db.String(20), default='1.0')
    status = db.Column(db.String(20), default='draft')
    scoring_mode = db.Column(db.String(20), default='none')
    total_max_score = db.Column(db.Numeric(10, 2))
    pass_score = db.Column(db.Numeric(10, 2))
    is_template = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    published_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 关系
    nodes = db.relationship('TemplateNode', backref='template', cascade='all, delete-orphan',
                           order_by='TemplateNode.sort_order')
    creator = db.relationship('User', backref='created_templates')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'industry_id': self.industry_id,
            'industry_name': self.industry.name if self.industry else None,
            'description': self.description,
            'version': self.version,
            'status': self.status,
            'scoring_mode': self.scoring_mode,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def get_tree(self):
        """获取模板的完整树形结构"""
        root_nodes = [n for n in self.nodes if n.parent_id is None]
        return [node.to_tree_dict() for node in sorted(root_nodes, key=lambda x: x.sort_order)]


class TemplateNode(db.Model):
    __tablename__ = 'template_nodes'

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('check_templates.id', ondelete='CASCADE'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('template_nodes.id', ondelete='CASCADE'))

    # 基本信息
    name = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    node_type = db.Column(db.String(20), nullable=False)  # 'category' or 'item'
    sort_order = db.Column(db.Integer, default=0)
    node_code = db.Column(db.String(50))

    # 检查方式配置（仅 item 有效）
    check_type = db.Column(db.String(20))
    is_required = db.Column(db.Boolean, default=False)

    # 打分配置
    max_score = db.Column(db.Numeric(10, 2))
    min_score = db.Column(db.Numeric(10, 2), default=0)
    score_step = db.Column(db.Numeric(10, 2), default=1)
    default_score = db.Column(db.Numeric(10, 2))
    score_weight = db.Column(db.Numeric(5, 2), default=1.0)

    # 单选配置
    radio_options = db.Column(db.JSON)
    default_radio = db.Column(db.String(50))

    # 数值配置
    numeric_min = db.Column(db.Numeric(15, 4))
    numeric_max = db.Column(db.Numeric(15, 4))
    numeric_unit = db.Column(db.String(30))
    numeric_precision = db.Column(db.Integer, default=2)

    # 多选配置
    multi_options = db.Column(db.JSON)

    # 文本配置
    text_placeholder = db.Column(db.String(500))
    text_min_length = db.Column(db.Integer, default=0)

    # 附件配置
    allow_attachment = db.Column(db.Boolean, default=False)
    attachment_required = db.Column(db.Boolean, default=False)
    max_attachments = db.Column(db.Integer, default=5)
    allowed_file_types = db.Column(db.String(200), default='image/*,.pdf,.doc,.docx,.xls,.xlsx')

    # 知识库
    legal_basis = db.Column(db.Text)
    standard_basis = db.Column(db.Text)
    regulation_basis = db.Column(db.Text)
    key_points = db.Column(db.Text)
    common_problems = db.Column(db.Text)
    reference_docs = db.Column(db.JSON)

    # AI 配置
    ai_enabled = db.Column(db.Boolean, default=True)
    ai_prompt_template = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 自引用关系
    children = db.relationship('TemplateNode',
                               backref=db.backref('parent', remote_side=[id]),
                               cascade='all, delete-orphan',
                               order_by='TemplateNode.sort_order')

    def to_dict(self):
        """平铺字典"""
        return {
            'id': self.id,
            'template_id': self.template_id,
            'parent_id': self.parent_id,
            'name': self.name,
            'description': self.description,
            'node_type': self.node_type,
            'sort_order': self.sort_order,
            'node_code': self.node_code,
            'check_type': self.check_type,
            'is_required': self.is_required,
            'max_score': float(self.max_score) if self.max_score else None,
            'min_score': float(self.min_score) if self.min_score else None,
            'score_step': float(self.score_step) if self.score_step else None,
            'radio_options': self.radio_options,
            'numeric_min': float(self.numeric_min) if self.numeric_min else None,
            'numeric_max': float(self.numeric_max) if self.numeric_max else None,
            'numeric_unit': self.numeric_unit,
            'multi_options': self.multi_options,
            'text_placeholder': self.text_placeholder,
            'allow_attachment': self.allow_attachment,
            'attachment_required': self.attachment_required,
            'max_attachments': self.max_attachments,
            'legal_basis': self.legal_basis,
            'standard_basis': self.standard_basis,
            'regulation_basis': self.regulation_basis,
            'key_points': self.key_points,
            'common_problems': self.common_problems,
            'ai_enabled': self.ai_enabled,
        }

    def to_tree_dict(self):
        """树形字典（递归包含子节点）"""
        data = self.to_dict()
        data['children'] = [child.to_tree_dict() for child in
                           sorted(self.children, key=lambda x: x.sort_order)]
        return data
```

### 5.4 `app/models/enterprise.py`

```python
from app.extensions import db
from datetime import datetime


class Enterprise(db.Model):
    __tablename__ = 'enterprises'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    unified_code = db.Column(db.String(50))
    industry_id = db.Column(db.Integer, db.ForeignKey('industries.id'))
    province = db.Column(db.String(50))
    city = db.Column(db.String(50))
    district = db.Column(db.String(50))
    address = db.Column(db.Text)
    contact_person = db.Column(db.String(50))
    contact_phone = db.Column(db.String(20))
    contact_email = db.Column(db.String(100))
    enterprise_type = db.Column(db.String(50))
    scale = db.Column(db.String(50))
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    inspections = db.relationship('Inspection', backref='enterprise')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'unified_code': self.unified_code,
            'industry_id': self.industry_id,
            'industry_name': self.industry.name if self.industry else None,
            'address': self.address,
            'contact_person': self.contact_person,
            'contact_phone': self.contact_phone,
        }
```

### 5.5 `app/models/inspection.py`

```python
from app.extensions import db
from datetime import datetime, date


class Inspection(db.Model):
    __tablename__ = 'inspections'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True)
    enterprise_id = db.Column(db.Integer, db.ForeignKey('enterprises.id'), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('check_templates.id'), nullable=False)
    inspector_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    inspection_date = db.Column(db.Date, default=date.today)
    inspection_type = db.Column(db.String(50))

    status = db.Column(db.String(20), default='in_progress')
    progress = db.Column(db.Integer, default=0)
    total_items = db.Column(db.Integer, default=0)
    completed_items = db.Column(db.Integer, default=0)

    total_score = db.Column(db.Numeric(10, 2))
    max_possible_score = db.Column(db.Numeric(10, 2))
    pass_count = db.Column(db.Integer, default=0)
    fail_count = db.Column(db.Integer, default=0)
    na_count = db.Column(db.Integer, default=0)

    overall_result = db.Column(db.String(20))
    overall_conclusion = db.Column(db.Text)
    remarks = db.Column(db.Text)

    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    reviewed_at = db.Column(db.DateTime)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    latitude = db.Column(db.Numeric(10, 7))
    longitude = db.Column(db.Numeric(10, 7))
    location_address = db.Column(db.String(500))

    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 关系
    template = db.relationship('CheckTemplate', backref='inspections')
    results = db.relationship('InspectionResult', backref='inspection', cascade='all, delete-orphan')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])

    def generate_code(self):
        """生成检查编号"""
        today = date.today().strftime('%Y%m%d')
        count = Inspection.query.filter(
            db.func.date(Inspection.created_at) == date.today()
        ).count()
        self.code = f"INS-{today}-{count + 1:03d}"

    def update_progress(self):
        """更新检查进度"""
        total = len([r for r in self.results])
        completed = len([r for r in self.results if r.is_completed])
        self.total_items = total
        self.completed_items = completed
        self.progress = int(completed / total * 100) if total > 0 else 0

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'enterprise_id': self.enterprise_id,
            'enterprise_name': self.enterprise.name if self.enterprise else None,
            'template_id': self.template_id,
            'template_name': self.template.name if self.template else None,
            'inspector_id': self.inspector_id,
            'inspector_name': self.inspector.real_name if self.inspector else None,
            'inspection_date': self.inspection_date.isoformat() if self.inspection_date else None,
            'status': self.status,
            'progress': self.progress,
            'total_score': float(self.total_score) if self.total_score else None,
            'overall_result': self.overall_result,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class InspectionResult(db.Model):
    __tablename__ = 'inspection_results'

    id = db.Column(db.Integer, primary_key=True)
    inspection_id = db.Column(db.Integer, db.ForeignKey('inspections.id', ondelete='CASCADE'), nullable=False)
    node_id = db.Column(db.Integer, db.ForeignKey('template_nodes.id'), nullable=False)

    node_name = db.Column(db.String(500))
    check_type = db.Column(db.String(20))

    # 结果值
    score_value = db.Column(db.Numeric(10, 2))
    radio_value = db.Column(db.String(50))
    numeric_value = db.Column(db.Numeric(15, 4))
    text_value = db.Column(db.Text)
    multi_value = db.Column(db.JSON)

    # 问题记录
    has_problem = db.Column(db.Boolean, default=False)
    problem_description = db.Column(db.Text)
    severity = db.Column(db.String(20))
    rectification_suggestion = db.Column(db.Text)

    # AI 辅助
    ai_generated = db.Column(db.Boolean, default=False)
    ai_suggestion = db.Column(db.Text)
    ai_reference = db.Column(db.Text)
    ai_used_at = db.Column(db.DateTime)

    is_completed = db.Column(db.Boolean, default=False)
    is_na = db.Column(db.Boolean, default=False)
    remarks = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 关系
    node = db.relationship('TemplateNode')
    attachments = db.relationship('Attachment', backref='result', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'inspection_id': self.inspection_id,
            'node_id': self.node_id,
            'node_name': self.node_name,
            'check_type': self.check_type,
            'score_value': float(self.score_value) if self.score_value else None,
            'radio_value': self.radio_value,
            'numeric_value': float(self.numeric_value) if self.numeric_value else None,
            'text_value': self.text_value,
            'multi_value': self.multi_value,
            'has_problem': self.has_problem,
            'problem_description': self.problem_description,
            'severity': self.severity,
            'rectification_suggestion': self.rectification_suggestion,
            'ai_generated': self.ai_generated,
            'ai_suggestion': self.ai_suggestion,
            'ai_reference': self.ai_reference,
            'is_completed': self.is_completed,
            'is_na': self.is_na,
            'attachments': [a.to_dict() for a in self.attachments],
        }
```

### 5.6 `app/models/attachment.py`

```python
from app.extensions import db
from datetime import datetime


class Attachment(db.Model):
    __tablename__ = 'attachments'

    id = db.Column(db.Integer, primary_key=True)
    inspection_result_id = db.Column(db.Integer,
                                      db.ForeignKey('inspection_results.id', ondelete='CASCADE'))
    file_name = db.Column(db.String(500), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(20), nullable=False)
    file_size = db.Column(db.Integer)
    mime_type = db.Column(db.String(100))
    thumbnail_path = db.Column(db.String(500))
    image_width = db.Column(db.Integer)
    image_height = db.Column(db.Integer)
    source = db.Column(db.String(20), default='upload')
    description = db.Column(db.String(500))
    sort_order = db.Column(db.Integer, default=0)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)

    uploader = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'file_name': self.file_name,
            'file_path': self.file_path,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'thumbnail_path': self.thumbnail_path,
            'source': self.source,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
```

---

## 六、核心配置文件

### 6.1 `app/config.py`

```python
import os
from datetime import timedelta


class Config:
    """基础配置"""
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
    
    # 数据库
    PG_HOST = os.getenv('PG_HOST', '62.234.0.182')
    PG_PORT = int(os.getenv('PG_PORT', 5432))
    PG_DB = os.getenv('PG_DB', 'expert_new_mvp1')
    PG_USER = os.getenv('PG_USER', 'expert_new_mvp1')
    PG_PASSWORD = os.getenv('PG_PASSWORD', '1234567890@sdtj')
    
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }
    
    # JWT（H5端认证）
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    JWT_EXPIRATION_HOURS = 72
    
    # 文件上传
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
    ALLOWED_DOC_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'}
    THUMBNAIL_SIZE = (200, 200)
    
    # AI 大模型配置（OpenAI 兼容）
    AI_API_BASE_URL = os.getenv('AI_API_BASE_URL', 'https://api.openai.com/v1')
    AI_API_KEY = os.getenv('AI_API_KEY', 'sk-your-api-key')
    AI_MODEL_NAME = os.getenv('AI_MODEL_NAME', 'gpt-4o-mini')
    AI_MAX_TOKENS = int(os.getenv('AI_MAX_TOKENS', 2000))
    AI_TEMPERATURE = float(os.getenv('AI_TEMPERATURE', 0.7))


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
```

### 6.2 `app/extensions.py`

```python
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'web_auth.login'
login_manager.login_message = '请先登录'
```

### 6.3 `app/__init__.py`（工厂函数）

```python
import os
from flask import Flask
from app.config import config_map
from app.extensions import db, migrate, login_manager


def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config_map.get(config_name, config_map['default']))

    # 初始化扩展
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # 确保上传目录存在
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'attachments'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'temp'), exist_ok=True)

    # 注册蓝图
    from app.web import web_bp
    from app.h5 import h5_bp
    from app.api import api_bp

    app.register_blueprint(web_bp)            # Web 管理端，前缀 /
    app.register_blueprint(h5_bp, url_prefix='/h5')      # H5 移动端页面
    app.register_blueprint(api_bp, url_prefix='/api/v1')  # REST API

    # 加载用户回调
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # 注册自定义模板过滤器/全局函数
    register_template_helpers(app)

    return app


def register_template_helpers(app):
    @app.template_filter('datetime_format')
    def datetime_format(value, fmt='%Y-%m-%d %H:%M'):
        if value:
            return value.strftime(fmt)
        return ''

    @app.template_filter('date_format')
    def date_format(value, fmt='%Y-%m-%d'):
        if value:
            return value.strftime(fmt)
        return ''
```

### 6.4 `run.py`

```python
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
```

### 6.5 `requirements.txt`

```
Flask>=3.0
Flask-SQLAlchemy>=3.1
Flask-Migrate>=4.0
Flask-Login>=0.6
Flask-WTF>=1.2
psycopg2-binary>=2.9
SQLAlchemy>=2.0
Werkzeug>=3.0
PyJWT>=2.8
openai>=1.0
Pillow>=10.0
python-dotenv>=1.0
gunicorn>=21.2
```

### 6.6 `.env.example`

```env
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-here

# PostgreSQL
PG_HOST=62.234.0.182
PG_PORT=5432
PG_DB=expert_new_mvp1
PG_USER=expert_new_mvp1
PG_PASSWORD=1234567890@sdtj

# AI 大模型（OpenAI 兼容接口）
AI_API_BASE_URL=https://api.openai.com/v1
AI_API_KEY=sk-your-api-key
AI_MODEL_NAME=gpt-4o-mini
AI_MAX_TOKENS=2000
AI_TEMPERATURE=0.7
```

---

## 七、核心业务服务层

### 7.1 `app/services/template_service.py` — 模板树形操作

```python
from app.extensions import db
from app.models.template import CheckTemplate, TemplateNode


class TemplateService:
    """模板管理服务 —— 处理树形结构的增删改查"""

    @staticmethod
    def get_templates_by_industry(industry_id=None, status='published'):
        """按行业分类获取模板列表"""
        query = CheckTemplate.query
        if industry_id:
            query = query.filter_by(industry_id=industry_id)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(CheckTemplate.updated_at.desc()).all()

    @staticmethod
    def get_template_tree(template_id):
        """获取模板完整树形结构"""
        template = CheckTemplate.query.get_or_404(template_id)
        # 一次性加载所有节点，避免 N+1 查询
        all_nodes = TemplateNode.query.filter_by(template_id=template_id)\
            .order_by(TemplateNode.sort_order).all()
        
        # 构建树
        node_map = {node.id: node for node in all_nodes}
        tree = []
        for node in all_nodes:
            node._children_list = []
        for node in all_nodes:
            if node.parent_id and node.parent_id in node_map:
                node_map[node.parent_id]._children_list.append(node)
            else:
                tree.append(node)
        
        def build_tree_dict(node):
            d = node.to_dict()
            d['children'] = [build_tree_dict(c) for c in 
                           sorted(node._children_list, key=lambda x: x.sort_order)]
            return d
        
        return {
            'template': template.to_dict(),
            'tree': [build_tree_dict(n) for n in sorted(tree, key=lambda x: x.sort_order)]
        }

    @staticmethod
    def add_node(template_id, parent_id, node_data):
        """添加节点"""
        # 计算 sort_order
        siblings = TemplateNode.query.filter_by(
            template_id=template_id, parent_id=parent_id
        ).count()
        
        node = TemplateNode(
            template_id=template_id,
            parent_id=parent_id,
            sort_order=siblings,
            **node_data
        )
        db.session.add(node)
        db.session.commit()
        return node

    @staticmethod
    def update_node(node_id, node_data):
        """更新节点"""
        node = TemplateNode.query.get_or_404(node_id)
        for key, value in node_data.items():
            if hasattr(node, key):
                setattr(node, key, value)
        db.session.commit()
        return node

    @staticmethod
    def delete_node(node_id):
        """删除节点（级联删除子节点）"""
        node = TemplateNode.query.get_or_404(node_id)
        db.session.delete(node)
        db.session.commit()

    @staticmethod
    def move_node(node_id, new_parent_id, new_sort_order):
        """移动节点（拖拽排序）"""
        node = TemplateNode.query.get_or_404(node_id)
        node.parent_id = new_parent_id
        node.sort_order = new_sort_order
        db.session.commit()

    @staticmethod
    def reorder_nodes(node_ids):
        """批量重排序"""
        for i, nid in enumerate(node_ids):
            node = TemplateNode.query.get(nid)
            if node:
                node.sort_order = i
        db.session.commit()

    @staticmethod
    def duplicate_template(template_id, new_name=None):
        """复制模板（深拷贝，包含所有节点）"""
        original = CheckTemplate.query.get_or_404(template_id)
        
        new_template = CheckTemplate(
            name=new_name or f"{original.name} (副本)",
            code=None,
            industry_id=original.industry_id,
            description=original.description,
            scoring_mode=original.scoring_mode,
            total_max_score=original.total_max_score,
            pass_score=original.pass_score,
            status='draft',
        )
        db.session.add(new_template)
        db.session.flush()  # 获取新 template_id
        
        # 复制所有节点，保持树形结构
        old_nodes = TemplateNode.query.filter_by(template_id=template_id)\
            .order_by(TemplateNode.id).all()
        
        id_mapping = {}  # old_id -> new_id
        for old_node in old_nodes:
            new_node = TemplateNode(
                template_id=new_template.id,
                parent_id=id_mapping.get(old_node.parent_id),
                name=old_node.name,
                description=old_node.description,
                node_type=old_node.node_type,
                sort_order=old_node.sort_order,
                node_code=old_node.node_code,
                check_type=old_node.check_type,
                is_required=old_node.is_required,
                max_score=old_node.max_score,
                min_score=old_node.min_score,
                score_step=old_node.score_step,
                radio_options=old_node.radio_options,
                numeric_min=old_node.numeric_min,
                numeric_max=old_node.numeric_max,
                numeric_unit=old_node.numeric_unit,
                multi_options=old_node.multi_options,
                text_placeholder=old_node.text_placeholder,
                allow_attachment=old_node.allow_attachment,
                attachment_required=old_node.attachment_required,
                max_attachments=old_node.max_attachments,
                legal_basis=old_node.legal_basis,
                standard_basis=old_node.standard_basis,
                regulation_basis=old_node.regulation_basis,
                key_points=old_node.key_points,
                common_problems=old_node.common_problems,
                reference_docs=old_node.reference_docs,
                ai_enabled=old_node.ai_enabled,
                ai_prompt_template=old_node.ai_prompt_template,
            )
            db.session.add(new_node)
            db.session.flush()
            id_mapping[old_node.id] = new_node.id
        
        db.session.commit()
        return new_template

    @staticmethod
    def get_item_nodes(template_id):
        """获取模板中所有检查项节点（不含分类节点）"""
        return TemplateNode.query.filter_by(
            template_id=template_id, node_type='item'
        ).order_by(TemplateNode.sort_order).all()
```

### 7.2 `app/services/inspection_service.py` — 检查执行

```python
from app.extensions import db
from app.models.inspection import Inspection, InspectionResult
from app.models.template import TemplateNode
from datetime import datetime, date


class InspectionService:
    """检查执行服务"""

    @staticmethod
    def create_inspection(enterprise_id, template_id, inspector_id, inspection_type=None):
        """创建检查任务，根据模板生成检查结果记录"""
        inspection = Inspection(
            enterprise_id=enterprise_id,
            template_id=template_id,
            inspector_id=inspector_id,
            inspection_date=date.today(),
            inspection_type=inspection_type,
            status='in_progress',
            started_at=datetime.now(),
        )
        inspection.generate_code()
        db.session.add(inspection)
        db.session.flush()

        # 获取模板中所有检查项，生成对应的结果记录
        item_nodes = TemplateNode.query.filter_by(
            template_id=template_id, node_type='item'
        ).order_by(TemplateNode.sort_order).all()

        for node in item_nodes:
            result = InspectionResult(
                inspection_id=inspection.id,
                node_id=node.id,
                node_name=node.name,
                check_type=node.check_type,
                is_completed=False,
            )
            db.session.add(result)

        inspection.total_items = len(item_nodes)
        db.session.commit()
        return inspection

    @staticmethod
    def save_result(result_id, data):
        """保存单项检查结果"""
        result = InspectionResult.query.get_or_404(result_id)

        # 根据 check_type 保存对应的值
        check_type = result.check_type
        if check_type == 'score':
            result.score_value = data.get('score_value')
        elif check_type == 'radio':
            result.radio_value = data.get('radio_value')
        elif check_type == 'numeric':
            result.numeric_value = data.get('numeric_value')
        elif check_type == 'text':
            result.text_value = data.get('text_value')
        elif check_type == 'multi_check':
            result.multi_value = data.get('multi_value')

        # 通用字段
        result.has_problem = data.get('has_problem', False)
        result.problem_description = data.get('problem_description')
        result.severity = data.get('severity')
        result.rectification_suggestion = data.get('rectification_suggestion')
        result.is_na = data.get('is_na', False)
        result.remarks = data.get('remarks')
        result.is_completed = True
        result.updated_at = datetime.now()

        # 更新检查进度
        inspection = result.inspection
        inspection.update_progress()

        db.session.commit()
        return result

    @staticmethod
    def save_ai_result(result_id, ai_suggestion, ai_reference):
        """保存 AI 生成的结果"""
        result = InspectionResult.query.get_or_404(result_id)
        result.ai_generated = True
        result.ai_suggestion = ai_suggestion
        result.ai_reference = ai_reference
        result.ai_used_at = datetime.now()
        db.session.commit()
        return result

    @staticmethod
    def complete_inspection(inspection_id, overall_conclusion=None, overall_result=None):
        """完成检查"""
        inspection = Inspection.query.get_or_404(inspection_id)
        inspection.status = 'completed'
        inspection.completed_at = datetime.now()
        inspection.overall_conclusion = overall_conclusion
        inspection.overall_result = overall_result
        inspection.update_progress()

        # 计算汇总数据
        results = InspectionResult.query.filter_by(inspection_id=inspection_id).all()
        inspection.pass_count = sum(1 for r in results if r.radio_value in ('pass', 'qualified', 'conform', '合格', '符合', '通过'))
        inspection.fail_count = sum(1 for r in results if r.radio_value in ('fail', 'unqualified', 'non_conform', '不合格', '不符合', '不通过'))
        inspection.na_count = sum(1 for r in results if r.is_na)

        # 计算总分（如果使用打分模式）
        score_results = [r for r in results if r.check_type == 'score' and r.score_value is not None]
        if score_results:
            inspection.total_score = sum(float(r.score_value) for r in score_results)

        db.session.commit()
        return inspection

    @staticmethod
    def get_inspection_detail(inspection_id):
        """获取检查详情（含树形结构的结果）"""
        inspection = Inspection.query.get_or_404(inspection_id)
        results = InspectionResult.query.filter_by(inspection_id=inspection_id).all()

        # 构建结果映射 (node_id -> result)
        result_map = {r.node_id: r.to_dict() for r in results}

        # 获取模板树形结构
        from app.services.template_service import TemplateService
        template_tree = TemplateService.get_template_tree(inspection.template_id)

        # 将结果合并到树中
        def merge_results(nodes):
            for node in nodes:
                if node['node_type'] == 'item' and node['id'] in result_map:
                    node['result'] = result_map[node['id']]
                if 'children' in node:
                    merge_results(node['children'])

        merge_results(template_tree['tree'])

        return {
            'inspection': inspection.to_dict(),
            'tree': template_tree['tree'],
        }

    @staticmethod
    def get_inspector_inspections(inspector_id, status=None):
        """获取专家的检查记录列表"""
        query = Inspection.query.filter_by(inspector_id=inspector_id)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(Inspection.created_at.desc()).all()
```

### 7.3 `app/services/ai_service.py` — AI 辅助

```python
import json
from datetime import datetime
from openai import OpenAI
from flask import current_app


class AIService:
    """AI 辅助检查服务"""

    @staticmethod
    def get_client():
        return OpenAI(
            api_key=current_app.config['AI_API_KEY'],
            base_url=current_app.config['AI_API_BASE_URL'],
        )

    @staticmethod
    def generate_check_conclusion(node_info, context=None):
        """
        为单个检查项生成AI辅助结论
        
        参数:
            node_info: dict, 包含检查项的完整信息
                - name: 检查项名称
                - description: 检查项描述
                - legal_basis: 法律依据
                - standard_basis: 标准依据
                - key_points: 检查要点
                - common_problems: 常见问题
                - check_type: 检查方式
                - radio_options: 选项（如有）
            context: dict, 可选，现场上下文信息
                - found_problems: 现场已发现的问题描述
                - enterprise_name: 企业名称
                - enterprise_type: 企业类型
                - inspection_type: 检查类型
        
        返回:
            dict: {
                'conclusion': str,    # 检查结论
                'problems': str,      # 发现的问题描述
                'suggestion': str,    # 整改建议
                'reference': str,     # 引用的标准/法规
                'severity': str,      # 问题严重程度建议
            }
        """
        client = AIService.get_client()

        # 构建系统提示
        system_prompt = """你是一位资深的现场检查/审核专家助手。你的任务是根据检查项目信息，帮助现场检查人员生成专业的检查结论。

你需要输出以下内容（JSON格式）：
1. conclusion: 检查结论（简洁专业的结论描述）
2. problems: 如有问题，描述发现的具体问题
3. suggestion: 整改建议（如有问题）
4. reference: 引用的法律法规或标准条款
5. severity: 问题严重程度（none/minor/major/critical），none表示无问题

请确保：
- 结论措辞专业、准确
- 引用的标准/法规要具体到条款号
- 整改建议要有可操作性
- 输出纯JSON，不要有其他内容"""

        # 构建用户提示
        user_parts = [f"## 检查项目\n{node_info.get('name', '')}"]

        if node_info.get('description'):
            user_parts.append(f"## 检查项描述\n{node_info['description']}")

        if node_info.get('legal_basis'):
            user_parts.append(f"## 法律依据\n{node_info['legal_basis']}")

        if node_info.get('standard_basis'):
            user_parts.append(f"## 标准依据\n{node_info['standard_basis']}")

        if node_info.get('key_points'):
            user_parts.append(f"## 检查要点\n{node_info['key_points']}")

        if node_info.get('common_problems'):
            user_parts.append(f"## 常见问题参考\n{node_info['common_problems']}")

        if context:
            if context.get('found_problems'):
                user_parts.append(f"## 现场已发现问题\n{context['found_problems']}")
            if context.get('enterprise_name'):
                user_parts.append(f"## 被检查企业\n{context['enterprise_name']}")
            if context.get('inspection_type'):
                user_parts.append(f"## 检查类型\n{context['inspection_type']}")

        user_parts.append("\n请基于以上信息，生成专业的检查结论（JSON格式）。")

        # 如果节点配置了自定义 AI 提示词，追加
        if node_info.get('ai_prompt_template'):
            user_parts.append(f"\n## 额外要求\n{node_info['ai_prompt_template']}")

        user_prompt = "\n\n".join(user_parts)

        try:
            response = client.chat.completions.create(
                model=current_app.config['AI_MODEL_NAME'],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=current_app.config['AI_MAX_TOKENS'],
                temperature=current_app.config['AI_TEMPERATURE'],
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            result = json.loads(content)

            return {
                'success': True,
                'conclusion': result.get('conclusion', ''),
                'problems': result.get('problems', ''),
                'suggestion': result.get('suggestion', ''),
                'reference': result.get('reference', ''),
                'severity': result.get('severity', 'none'),
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }

    @staticmethod
    def generate_overall_conclusion(inspection_data):
        """
        生成检查总体结论
        
        参数:
            inspection_data: dict, 包含整个检查的汇总信息
        """
        client = AIService.get_client()

        system_prompt = """你是一位资深的现场检查/审核专家助手。请根据检查汇总数据，生成一份专业的总体检查结论。
结论应包含：
1. 总体评价
2. 主要发现的问题汇总
3. 总体整改建议
4. 结论性判定

请输出JSON格式：
{
    "overall_evaluation": "总体评价",
    "key_findings": "主要发现",
    "recommendations": "整改建议",
    "result": "pass/fail/conditional"
}"""

        user_prompt = json.dumps(inspection_data, ensure_ascii=False, indent=2)

        try:
            response = client.chat.completions.create(
                model=current_app.config['AI_MODEL_NAME'],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=current_app.config['AI_MAX_TOKENS'],
                temperature=current_app.config['AI_TEMPERATURE'],
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            return {'success': True, 'data': json.loads(content)}

        except Exception as e:
            return {'success': False, 'error': str(e)}
```

### 7.4 `app/services/file_service.py` — 文件上传

```python
import os
import uuid
from datetime import datetime
from PIL import Image
from flask import current_app
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.attachment import Attachment


class FileService:
    """文件上传与管理服务"""

    @staticmethod
    def allowed_file(filename):
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        allowed = current_app.config['ALLOWED_IMAGE_EXTENSIONS'] | current_app.config['ALLOWED_DOC_EXTENSIONS']
        return ext in allowed

    @staticmethod
    def get_file_type(filename):
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        if ext in current_app.config['ALLOWED_IMAGE_EXTENSIONS']:
            return 'image'
        return 'document'

    @staticmethod
    def save_file(file, result_id, user_id, source='upload'):
        """
        保存上传的文件
        
        参数:
            file: FileStorage 对象
            result_id: 关联的检查结果ID
            user_id: 上传者ID
            source: 'upload' 或 'camera'
        """
        if not file or not FileService.allowed_file(file.filename):
            raise ValueError("不支持的文件类型")

        # 生成安全的文件名
        original_name = secure_filename(file.filename)
        ext = original_name.rsplit('.', 1)[1].lower() if '.' in original_name else 'jpg'
        unique_name = f"{uuid.uuid4().hex}.{ext}"

        # 按日期分目录
        date_dir = datetime.now().strftime('%Y/%m/%d')
        save_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'attachments', date_dir)
        os.makedirs(save_dir, exist_ok=True)

        file_path = os.path.join(save_dir, unique_name)
        file.save(file_path)

        # 获取文件信息
        file_size = os.path.getsize(file_path)
        file_type = FileService.get_file_type(file.filename)
        relative_path = os.path.join('attachments', date_dir, unique_name)

        # 如果是图片，生成缩略图
        thumbnail_path = None
        image_width = None
        image_height = None
        if file_type == 'image':
            try:
                img = Image.open(file_path)
                image_width, image_height = img.size

                # 生成缩略图
                thumb_name = f"thumb_{unique_name}"
                thumb_full_path = os.path.join(save_dir, thumb_name)
                img.thumbnail(current_app.config['THUMBNAIL_SIZE'])
                img.save(thumb_full_path)
                thumbnail_path = os.path.join('attachments', date_dir, thumb_name)
            except Exception:
                pass

        # 创建数据库记录
        attachment = Attachment(
            inspection_result_id=result_id,
            file_name=file.filename,
            file_path=relative_path,
            file_type=file_type,
            file_size=file_size,
            mime_type=file.content_type,
            thumbnail_path=thumbnail_path,
            image_width=image_width,
            image_height=image_height,
            source=source,
            uploaded_by=user_id,
        )
        db.session.add(attachment)
        db.session.commit()

        return attachment

    @staticmethod
    def delete_file(attachment_id):
        """删除附件"""
        attachment = Attachment.query.get_or_404(attachment_id)

        # 删除物理文件
        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], attachment.file_path)
        if os.path.exists(full_path):
            os.remove(full_path)

        # 删除缩略图
        if attachment.thumbnail_path:
            thumb_path = os.path.join(current_app.config['UPLOAD_FOLDER'], attachment.thumbnail_path)
            if os.path.exists(thumb_path):
                os.remove(thumb_path)

        db.session.delete(attachment)
        db.session.commit()
```

---

## 八、路由设计

### 8.1 Web 管理端路由 (React Router)

| 路由 | 页面组件 | 说明 |
|---|---|---|
| `/login` | Login | 登录页 |
| `/` | Dashboard | 仪表盘 |
| `/templates` | Templates | 模板列表 |
| `/templates/:id` | TemplateEditor | 模板详情/树形编辑 |
| `/enterprises` | Enterprises | 企业列表 |
| `/enterprises/:id` | EnterpriseDetail | 企业详情 |
| `/tasks` | Tasks | 任务列表 |
| `/tasks/:id` | TaskDetail | 任务详情 |
| `/records` | Records | 检查记录列表 |
| `/records/:id` | RecordDetail | 记录详情 |
| `/knowledge` | Knowledge | 知识库 |
| `/analytics` | Analytics | 数据分析 |
| `/inspection` | Inspection | 检查执行 |

### 8.2 H5 移动端路由 (Vue Router)

| 路由 | 页面组件 | 说明 |
|---|---|---|
| `/login` | Login | 登录页 |
| `/` | Home | 首页 |
| `/tasks` | Tasks | 任务列表 |
| `/tasks/:id` | TaskDetail | 任务详情 |
| `/select-enterprise` | SelectEnterprise | 选择企业 |
| `/select-template` | SelectTemplate | 选择模板 |
| `/inspection/:id` | InspectionExecution | 检查执行页 |
| `/inspection/:id/item/:itemId` | InspectItem | 单项检查页 |
| `/records` | Records | 检查记录列表 |
| `/records/:id` | RecordDetail | 记录详情 |
| `/profile` | Profile | 个人中心 |
| `/about` | About | 关于 |
| `/settings` | Settings | 设置 |
| `/statistics` | Statistics | 统计 |

### 8.3 后端 API 路由 (FastAPI)

| 路由 | 方法 | 说明 | 请求/响应 |
|---|---|---|---|
| `/api/auth/login` | POST | 登录获取Token | `{username, password}` → `{access_token, user}` |
| `/api/auth/me` | GET | 获取当前用户信息 | `{user}` |
| `/api/templates` | GET | 模板列表 | `?category=` → `[{template}]` |
| `/api/templates` | POST | 创建模板 | `{template}` → `{template}` |
| `/api/templates/{id}` | GET | 模板详情 | `{template, items}` |
| `/api/templates/{id}` | PUT | 更新模板 | `{template}` → `{template}` |
| `/api/templates/{id}` | DELETE | 删除模板 | - |
| `/api/templates/{id}/tree` | GET | 模板树形结构 | `{template, tree}` |
| `/api/templates/{id}/items` | POST | 添加模板节点 | `{item}` → `{item}` |
| `/api/templates/items/{id}` | PUT | 更新节点 | `{item}` → `{item}` |
| `/api/templates/items/{id}` | DELETE | 删除节点 | - |
| `/api/enterprises` | GET | 企业列表 | `?keyword=` → `[{enterprise}]` |
| `/api/enterprises` | POST | 创建企业 | `{enterprise}` → `{enterprise}` |
| `/api/enterprises/{id}` | GET | 企业详情 | `{enterprise}` |
| `/api/enterprises/{id}` | PUT | 更新企业 | `{enterprise}` → `{enterprise}` |
| `/api/enterprises/{id}` | DELETE | 删除企业 | - |
| `/api/tasks` | GET | 任务列表 | `?status=` → `[{task}]` |
| `/api/tasks` | POST | 创建任务 | `{enterprise_id, template_id}` → `{task}` |
| `/api/tasks/{id}` | GET | 任务详情 | `{task, items}` |
| `/api/tasks/{id}/complete` | POST | 完成任务 | `{overall_conclusion}` → `{task}` |
| `/api/records` | GET | 检查记录列表 | `?status=` → `[{record}]` |
| `/api/records/{id}` | GET | 记录详情 | `{record, items}` |
| `/api/records/{id}/items/{item_id}` | PUT | 保存检查结果 | `{result}` → `{result}` |
| `/api/media/upload` | POST | 上传文件 | `multipart/form-data` → `{file}` |
| `/api/llm/generate` | POST | AI生成检查结论 | `{item_id, context}` → `{conclusion}` |
| `/api/ai-extract` | POST | AI提取模板 | `{file}` → `{items}` |
| `/api/knowledge` | GET | 知识库列表 | `[{knowledge}]` |
| `/api/analytics/overview` | GET | 数据概览 | `{stats}` |

---

## 九、API 实现示例

### 9.1 `backend/app/main.py` — FastAPI 应用入口

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, templates, enterprises, tasks, records, media, llm, ai_extract, knowledge, analytics
from app.database import engine, Base

app = FastAPI(
    title="专家辅助检查工作系统 API",
    description="MVP 版本 API 文档",
    version="1.0.0",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(templates.router, prefix="/api/templates", tags=["模板管理"])
app.include_router(enterprises.router, prefix="/api/enterprises", tags=["企业管理"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["任务管理"])
app.include_router(records.router, prefix="/api/records", tags=["检查记录"])
app.include_router(media.router, prefix="/api/media", tags=["文件上传"])
app.include_router(llm.router, prefix="/api/llm", tags=["AI/LLM"])
app.include_router(ai_extract.router, prefix="/api/ai-extract", tags=["AI提取"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["知识库"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["数据分析"])


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/")
async def root():
    return {"message": "专家辅助检查工作系统 API", "docs": "/docs"}
```

### 9.2 `backend/app/utils/security.py` — JWT 认证工具

```python
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User

# 配置
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="用户已被禁用")
    
    return user
```

### 9.3 `backend/app/routers/auth.py` — 认证路由

```python
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.utils.security import verify_password, create_access_token, get_current_user

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: Optional[str]
    full_name: Optional[str]
    role: str
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == request.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="账号已被禁用")
    
    access_token = create_access_token(data={"sub": str(user.id)})
    
    return TokenResponse(
        access_token=access_token,
        user=UserResponse.from_orm(user)
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.from_orm(current_user)
```

### 9.4 `backend/app/routers/tasks.py` — 任务管理路由

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app.models.user import User
from app.models.task import InspectionTask, TaskItemRecord
from app.models.template import InspectionTemplate, TemplateItem
from app.utils.security import get_current_user

router = APIRouter()


class TaskCreate(BaseModel):
    enterprise_id: str
    template_id: str
    inspection_type: Optional[str] = None


class TaskResponse(BaseModel):
    id: str
    enterprise_id: str
    template_id: str
    inspector_id: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.post("", response_model=TaskResponse)
async def create_task(
    request: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    task = InspectionTask(
        enterprise_id=request.enterprise_id,
        template_id=request.template_id,
        inspector_id=current_user.id,
        status="pending",
    )
    db.add(task)
    await db.flush()
    
    result = await db.execute(
        select(TemplateItem).where(TemplateItem.template_id == request.template_id)
    )
    items = result.scalars().all()
    
    for item in items:
        record = TaskItemRecord(
            task_id=task.id,
            template_item_id=item.id,
        )
        db.add(record)
    
    await db.commit()
    await db.refresh(task)
    
    return TaskResponse.from_orm(task)


@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(InspectionTask).where(InspectionTask.inspector_id == current_user.id)
    if status:
        query = query.where(InspectionTask.status == status)
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    return [TaskResponse.from_orm(t) for t in tasks]


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(InspectionTask).where(InspectionTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return task


@router.post("/{task_id}/complete")
async def complete_task(
    task_id: str,
    overall_conclusion: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(InspectionTask).where(InspectionTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task.status = "completed"
    task.completed_at = datetime.utcnow()
    if overall_conclusion:
        task.overall_conclusion = overall_conclusion
    
    await db.commit()
    
    return {"message": "任务已完成", "task_id": task_id}
```

### 9.5 `backend/app/routers/llm.py` — AI/LLM 路由

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.models.task import TaskItemRecord
from app.services.llm_service import LLMService
from app.utils.security import get_current_user

router = APIRouter()


class GenerateRequest(BaseModel):
    item_id: str
    context: Optional[dict] = None


@router.post("/generate")
async def generate_conclusion(
    request: GenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TaskItemRecord).where(TaskItemRecord.id == request.item_id)
    )
    record = result.scalar_one_or_none()
    
    if not record:
        return {"success": False, "error": "记录不存在"}
    
    conclusion = await LLMService.generate_check_conclusion(
        record=record,
        context=request.context
    )
    
    if conclusion["success"]:
        record.ai_suggestion = conclusion.get("conclusion", "")
        await db.commit()
    
    return conclusion
```

---

## 十、前端页面设计

### 10.1 Web 端 — 模板树形编辑器（核心页面）

文件: `app/templates/web/template/detail.html`

**设计要点**:

1. **左侧**: 树形导航（使用 jsTree 或自定义递归组件），显示模板的所有层级节点
2. **右侧**: 节点编辑面板，根据 `node_type` 和 `check_type` 动态显示不同的配置字段
3. **工具栏**: 添加同级节点、添加子节点、删除节点、拖拽排序、展开/折叠全部

```
┌──────────────────────────────────────────────────────────┐
│  模板名称: 食品安全日常监督检查表  [编辑] [发布] [复制]      │
├────────────────┬─────────────────────────────────────────┤
│  模板结构       │  节点编辑                                │
│  ┌──────────┐  │  ┌─────────────────────────────────┐    │
│  │▼ 一、许可   │  │  名称: [___________________]     │    │
│  │  ├ 1.1营..  │  │  类型: ○分类节点 ●检查项        │    │
│  │  ├ 1.2许..  │  │  检查方式: [单选判定 ▼]          │    │
│  │  └ 1.3经..  │  │  选项: [合格|不合格|不适用]      │    │
│  │▼ 二、环境   │  │  是否必填: ☑                     │    │
│  │  ├ 2.1场..  │  │  ── 附件配置 ──                  │    │
│  │  └ 2.2设..  │  │  允许附件: ☑  必须上传: ☐       │    │
│  │▼ 三、原料   │  │  ── 知识库 ──                    │    │
│  │  ...        │  │  法律依据: [textarea]            │    │
│  │             │  │  标准依据: [textarea]            │    │
│  │ [+大类]     │  │  检查要点: [textarea]            │    │
│  │             │  │  ── AI配置 ──                    │    │
│  │             │  │  启用AI: ☑                       │    │
│  │             │  │  [保存节点]                       │    │
│  └──────────┘  │  └─────────────────────────────────┘    │
└────────────────┴─────────────────────────────────────────┘
```

**关键交互逻辑**:

```javascript
// static/js/web/template_tree.js

// 1. 加载树形数据
async function loadTree(templateId) {
    const resp = await fetch(`/api/v1/templates/${templateId}/tree`);
    const data = await resp.json();
    renderTree(data.tree);
}

// 2. 点击节点 → 右侧加载节点详情
function onNodeClick(nodeId) {
    // 加载节点数据到右侧编辑面板
    // 根据 node_type 显示/隐藏不同字段
    // 根据 check_type 显示对应的配置区域
}

// 3. 根据 check_type 动态显示配置
function onCheckTypeChange(checkType) {
    hideAllCheckConfig();
    switch(checkType) {
        case 'score':
            showScoreConfig();  // 显示: 最高分、最低分、步长
            break;
        case 'radio':
            showRadioConfig();  // 显示: 选项列表（可增减）
            break;
        case 'numeric':
            showNumericConfig(); // 显示: 上限、下限、单位
            break;
        case 'text':
            showTextConfig();   // 显示: 提示文字、最少字数
            break;
        case 'multi_check':
            showMultiConfig();  // 显示: 多选选项列表
            break;
    }
}

// 4. 添加子节点
async function addChildNode(parentId) {
    const data = { name: '新检查项', node_type: 'item', check_type: 'radio' };
    await fetch(`/templates/${templateId}/nodes`, {
        method: 'POST',
        body: JSON.stringify({ parent_id: parentId, ...data }),
    });
    loadTree(templateId);
}

// 5. 拖拽排序（使用 SortableJS）
```

### 10.2 H5 移动端 — 页面设计

#### 10.2.1 基础布局 `h5/base.html`

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{% block title %}专家检查系统{% endblock %}</title>
    <!-- Vant 4 CSS -->
    <link rel="stylesheet" href="https://fastly.jsdelivr.net/npm/vant@4/lib/index.css">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/h5.css') }}">
    {% block head %}{% endblock %}
</head>
<body>
    <div id="app">
        {% block content %}{% endblock %}
    </div>

    <!-- Vue 3 -->
    <script src="https://fastly.jsdelivr.net/npm/vue@3/dist/vue.global.prod.js"></script>
    <!-- Vant 4 -->
    <script src="https://fastly.jsdelivr.net/npm/vant@4/lib/vant.min.js"></script>
    <!-- Axios -->
    <script src="https://fastly.jsdelivr.net/npm/axios/dist/axios.min.js"></script>

    <script>
        // 全局配置
        const API_BASE = '/api/v1';
        const TOKEN = localStorage.getItem('token');

        // Axios 默认配置
        axios.defaults.baseURL = API_BASE;
        if (TOKEN) {
            axios.defaults.headers.common['Authorization'] = `Bearer ${TOKEN}`;
        }

        // Token 过期处理
        axios.interceptors.response.use(
            response => response,
            error => {
                if (error.response && error.response.status === 401) {
                    localStorage.removeItem('token');
                    window.location.href = '/h5/login';
                }
                return Promise.reject(error);
            }
        );
    </script>

    {% block scripts %}{% endblock %}
</body>
</html>
```

#### 10.2.2 检查执行页 `h5/inspect.html`（核心页面）

**页面结构设计**:

```
┌─────────────────────────────┐
│  ← 返回    现场检查    完成  │  导航栏
├─────────────────────────────┤
│  XX食品有限公司              │  企业信息
│  食品安全日常检查表           │  模板名
│  进度: ████████░░ 80%       │  进度条
├─────────────────────────────┤
│                              │
│  ▼ 一、许可情况              │  可折叠的分类
│    ┌───────────────────┐     │
│    │ 1.1 营业执照     ✓ │     │  检查项卡片
│    │    [合格] ✅         │     │  （显示结果状态）
│    └───────────────────┘     │
│    ┌───────────────────┐     │
│    │ 1.2 许可证有效性  ○ │     │  未完成的项
│    │    点击进入检查 →    │     │
│    └───────────────────┘     │
│                              │
│  ▼ 二、环境卫生              │
│    ┌───────────────────┐     │
│    │ 2.1 场所卫生     ○ │     │
│    │    点击进入检查 →    │     │
│    └───────────────────┘     │
│    ...                       │
│                              │
├─────────────────────────────┤
│  [完成检查]                  │  底部按钮
└─────────────────────────────┘
```

**Vue 3 逻辑要点**:

```javascript
// 检查执行页 Vue 应用
const { createApp, ref, computed, onMounted } = Vue;

const app = createApp({
    setup() {
        const inspection = ref(null);
        const tree = ref([]);
        const loading = ref(true);

        // 加载检查数据
        const loadData = async () => {
            const { data } = await axios.get(`/inspections/${inspectionId}`);
            inspection.value = data.inspection;
            tree.value = data.tree;
            loading.value = false;
        };

        // 计算进度
        const progress = computed(() => {
            if (!inspection.value) return 0;
            return inspection.value.progress;
        });

        // 跳转到单项检查
        const goToItem = (resultId) => {
            window.location.href = `/h5/inspect/${inspectionId}/item/${resultId}`;
        };

        // 完成检查
        const completeInspection = async () => {
            // 弹出确认对话框
            // 调用 API 完成检查
        };

        onMounted(loadData);

        return { inspection, tree, loading, progress, goToItem, completeInspection };
    }
});

app.use(vant);
app.mount('#app');
```

#### 10.2.3 单项检查页 `h5/inspect_item.html`（最核心交互页）

**页面结构设计**:

```
┌─────────────────────────────┐
│  ← 返回    检查项详情   保存 │
├─────────────────────────────┤
│                              │
│  1.2 食品经营许可证          │  检查项名称
│  检查许可证是否在有效期内...  │  描述
│                              │
│  ┌─ 知识库支撑 ───────────┐ │  可展开的知识库
│  │  📋 法律依据:           │ │
│  │  《食品安全法》第35条... │ │
│  │  📐 标准依据:           │ │
│  │  GB 14881-2013...      │ │
│  │  🔍 检查要点:           │ │
│  │  1. 查看许可证原件      │ │
│  │  2. 核对经营范围        │ │
│  └─────────────────────────┘ │
│                              │
│  ── 检查结论 ──             │
│  ┌─────────────────────────┐ │  根据 check_type 动态渲染
│  │ ○ 合格  ○ 不合格  ○ 不适用│ │  这里是 radio 类型的示例
│  └─────────────────────────┘ │
│                              │
│  ── 问题描述（如有）──       │
│  ┌─────────────────────────┐ │
│  │ [textarea 输入框]        │ │
│  └─────────────────────────┘ │
│                              │
│  ── 附件 ──                  │
│  ┌─────┐ ┌─────┐ ┌─────┐   │
│  │ 📷  │ │ img │ │ img │   │  照片预览
│  │ 拍照 │ │     │ │     │   │
│  └─────┘ └─────┘ └─────┘   │
│                              │
│  ┌─────────────────────────┐ │
│  │   🤖 AI 生成检查结论     │ │  AI 按钮
│  └─────────────────────────┘ │
│                              │
│  ┌─────────────────────────┐ │
│  │       保存结果            │ │
│  └─────────────────────────┘ │
└─────────────────────────────┘
```

**动态表单渲染逻辑**（根据 `check_type` 渲染不同输入组件）:

```javascript
// 根据检查类型渲染对应的输入组件
const renderCheckInput = (checkType, nodeConfig) => {
    switch (checkType) {
        case 'score':
            // 渲染: 滑块 或 步进器
            // Vant: <van-stepper v-model="result.score_value" :min="0" :max="maxScore" :step="step" />
            break;
        
        case 'radio':
            // 渲染: 单选按钮组
            // Vant: <van-radio-group v-model="result.radio_value">
            //         <van-radio v-for="opt in options" :name="opt.value">{{ opt.label }}</van-radio>
            //       </van-radio-group>
            break;
        
        case 'numeric':
            // 渲染: 数值输入框 + 上下限提示 + 单位
            // Vant: <van-field v-model="result.numeric_value" type="number" :placeholder="`范围: ${min}-${max} ${unit}`" />
            // 输入后自动校验是否在范围内，超出范围高亮提醒
            break;
        
        case 'text':
            // 渲染: 多行文本输入
            // Vant: <van-field v-model="result.text_value" type="textarea" rows="4" :placeholder="placeholder" />
            break;
        
        case 'multi_check':
            // 渲染: 多选复选框组
            // Vant: <van-checkbox-group v-model="result.multi_value">
            //         <van-checkbox v-for="opt in options" :name="opt.value">{{ opt.label }}</van-checkbox>
            //       </van-checkbox-group>
            break;
    }
};
```

**AI 调用交互**:

```javascript
// AI 生成检查结论
const callAI = async () => {
    aiLoading.value = true;
    try {
        const { data } = await axios.post(`/results/${resultId}/ai`, {
            found_problems: result.value.problem_description || '',
        });
        
        if (data.success) {
            // 显示 AI 建议面板
            aiResult.value = data.ai_result;
            showAIPanel.value = true;
            
            // 用户可以选择"采纳"或"修改后采纳"
            // 采纳后自动填充到对应字段
        }
    } catch (e) {
        vant.showToast('AI 生成失败，请稍后重试');
    } finally {
        aiLoading.value = false;
    }
};

// 采纳 AI 建议
const acceptAISuggestion = () => {
    // 将 AI 结论填充到 text_value 或 problem_description
    result.value.text_value = aiResult.value.conclusion;
    result.value.problem_description = aiResult.value.problems;
    result.value.rectification_suggestion = aiResult.value.suggestion;
    result.value.ai_generated = true;
    showAIPanel.value = false;
    vant.showToast('已采纳 AI 建议');
};
```

**拍照上传交互**:

```javascript
// 拍照功能 - 调用手机摄像头
const takePhoto = () => {
    // 使用 HTML5 input[type=file][capture=camera]
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.capture = 'camera';  // 直接调起摄像头
    input.onchange = (e) => uploadFile(e.target.files[0], 'camera');
    input.click();
};

// 选择文件上传
const selectFile = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*,.pdf,.doc,.docx';
    input.onchange = (e) => uploadFile(e.target.files[0], 'upload');
    input.click();
};

// 上传文件
const uploadFile = async (file, source) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('result_id', resultId);
    formData.append('source', source);

    try {
        const { data } = await axios.post('/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
        attachments.value.push(data.attachment);
        vant.showToast('上传成功');
    } catch (e) {
        vant.showToast('上传失败');
    }
};
```

---

## 十一、Web 端页面实现要点

### 11.1 仪表盘 `web/dashboard.html`

显示内容:
- 统计卡片: 模板总数、进行中的检查、已完成的检查、本月检查数
- 最近检查记录列表
- 快速操作入口

### 11.2 模板列表 `web/template/list.html`

功能:
- 按行业分类筛选
- 按状态筛选 (草稿/已发布/已归档)
- 搜索
- 操作: 查看详情、编辑、发布、复制、删除

### 11.3 检查记录详情 `web/inspection/detail.html`

功能:
- 显示检查基本信息 (企业、模板、专家、日期、状态)
- 按模板树形结构展示所有检查结果
- 每个检查项显示: 结论值、问题描述、AI标记、附件预览
- 导出功能 (预留)

---

## 十二、关键实现注意事项

### 12.1 模板节点的树形操作

```python
# 在 app/utils/tree.py 中提供工具函数

def list_to_tree(flat_list, id_key='id', parent_key='parent_id'):
    """将平铺列表转为树形结构"""
    node_map = {item[id_key]: {**item, 'children': []} for item in flat_list}
    tree = []
    for item in flat_list:
        node = node_map[item[id_key]]
        parent_id = item[parent_key]
        if parent_id and parent_id in node_map:
            node_map[parent_id]['children'].append(node)
        else:
            tree.append(node)
    return tree


def tree_to_list(tree, parent_id=None):
    """将树形结构展平为列表"""
    result = []
    for node in tree:
        node_flat = {k: v for k, v in node.items() if k != 'children'}
        node_flat['parent_id'] = parent_id
        result.append(node_flat)
        if node.get('children'):
            result.extend(tree_to_list(node['children'], parent_id=node['id']))
    return result


def generate_node_codes(tree, prefix=''):
    """自动生成节点编号（如 1, 1.1, 1.2, 2, 2.1...）"""
    for i, node in enumerate(tree, 1):
        code = f"{prefix}{i}" if prefix else str(i)
        node['node_code'] = code
        if node.get('children'):
            generate_node_codes(node['children'], prefix=f"{code}.")
```

### 12.2 H5 端认证流程

```
1. 用户打开 /h5/login
2. 输入用户名密码，调用 POST /api/v1/auth/login
3. 获取 JWT Token，存储到 localStorage
4. 后续所有 API 请求在 Header 中携带 Authorization: Bearer <token>
5. Token 过期 → 自动跳转登录页
```

### 12.3 文件上传路径规则

```
uploads/
  attachments/
    2025/
      01/
        15/
          abc123def.jpg           # 原图
          thumb_abc123def.jpg     # 缩略图
```

### 12.4 静态文件服务

```python
# 在 Flask 中配置上传文件的访问
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
```

### 12.5 数据库初始化脚本

```python
# app/utils/init_db.py

def init_data():
    """初始化基础数据"""
    from app.extensions import db
    from app.models.user import User
    from app.models.industry import Industry

    # 创建默认管理员
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            real_name='系统管理员',
            role='admin',
        )
        admin.set_password('admin123')
        db.session.add(admin)

    # 创建默认行业分类
    default_industries = [
        {'name': '食品安全', 'code': 'food_safety', 'sort_order': 1},
        {'name': '安全生产', 'code': 'work_safety', 'sort_order': 2},
        {'name': 'ISO认证审核', 'code': 'iso_audit', 'sort_order': 3},
        {'name': '环境保护', 'code': 'environment', 'sort_order': 4},
        {'name': '消防安全', 'code': 'fire_safety', 'sort_order': 5},
    ]
    for ind_data in default_industries:
        if not Industry.query.filter_by(code=ind_data['code']).first():
            industry = Industry(**ind_data)
            db.session.add(industry)

    db.session.commit()
```

---

## 十三、开发步骤与里程碑

### Phase 1: 基础框架搭建（第 1 步）

```
□ 创建项目目录结构
□ 编写 requirements.txt 并安装依赖
□ 编写 config.py / extensions.py / __init__.py
□ 编写所有 ORM 模型 (models/)
□ 配置 Flask-Migrate，生成并执行数据库迁移
□ 验证数据库连接和表创建成功
□ 编写初始化数据脚本（管理员账号、默认行业分类）
□ 编写 run.py，确保应用可以启动
```

**验证标准**: 应用启动成功，数据库表全部创建，可以通过 Flask shell 操作数据。

### Phase 2: Web 端 — 用户认证 & 基础管理（第 2 步）

```
□ 编写 Web 端基础布局模板 (base.html, 含 Bootstrap 5)
□ 实现登录/登出功能 (Flask-Login)
□ 实现仪表盘页面
□ 实现行业分类 CRUD
□ 实现用户管理 CRUD
□ 实现企业管理 CRUD
```

**验证标准**: 管理员可以登录后台，管理行业分类、用户、企业信息。

### Phase 3: Web 端 — 模板管理核心（第 3 步，最重要）

```
□ 实现模板列表页（按行业筛选、按状态筛选）
□ 实现模板创建/编辑基本信息
□ 实现模板详情页 — 树形结构展示
□ 实现添加根节点（大类）
□ 实现添加子节点（层级嵌套）
□ 实现节点编辑 — 分类节点配置
□ 实现节点编辑 — 检查项配置（5 种 check_type 的表单联动）
□ 实现节点编辑 — 知识库信息录入
□ 实现节点编辑 — AI 配置
□ 实现节点编辑 — 附件配置
□ 实现节点删除（级联）
□ 实现节点拖拽排序
□ 实现模板发布/归档状态管理
□ 实现模板复制
```

**验证标准**: 可以在 Web 端创建一套完整的多层级检查模板，配置各种检查类型、知识库内容。

### Phase 4: H5 端 — 核心检查流程（第 4 步）

```
□ 编写 H5 基础布局 (base.html, 含 Vue 3 + Vant 4 CDN)
□ 实现 H5 登录页 (JWT 认证)
□ 实现 API: 登录、获取用户信息
□ 实现 H5 首页
□ 实现新建检查: 选择企业 → 选择模板 → 创建检查任务
□ 实现 API: 创建检查任务（根据模板生成结果记录）
□ 实现检查执行页: 按树形结构展示检查项列表
□ 实现单项检查页: 
  □ 知识库展示（法律依据、标准依据、检查要点）
  □ 打分类型输入 (Stepper)
  □ 单选判定输入 (RadioGroup)
  □ 数值输入 (Field + 范围校验)
  □ 文本描述输入 (Textarea)
  □ 多选输入 (CheckboxGroup)
  □ 问题描述录入
  □ 保存结果
□ 实现检查进度更新
□ 实现完成检查功能
```

**验证标准**: 专家可以在 H5 端完成一次完整的检查流程。

### Phase 5: 附件上传（第 5 步）

```
□ 实现文件上传 API
□ H5 端: 实现选择文件上传
□ H5 端: 实现调用摄像头拍照上传
□ H5 端: 实现附件预览和删除
□ Web 端: 检查详情页展示附件
□ 实现缩略图生成
```

**验证标准**: 可以在检查项中拍照或上传文件，并在 Web 端查看。

### Phase 6: AI 辅助功能（第 6 步）

```
□ 实现 AI Service (OpenAI 兼容接口调用)
□ 实现单项 AI 结论生成 API
□ H5 端: 单项检查页增加 AI 按钮
□ H5 端: AI 结果展示面板
□ H5 端: 采纳/修改 AI 建议
□ 实现总体结论 AI 生成
□ AI 调用记录保存
```

**验证标准**: 点击 AI 按钮可以生成检查结论，包含引用的法规标准。

### Phase 7: Web 端检查记录查看 & 收尾（第 7 步）

```
□ Web 端: 检查记录列表（筛选、搜索）
□ Web 端: 检查记录详情页（树形展示结果）
□ 数据统计仪表盘完善
□ 错误处理与异常页面
□ 生产环境配置 (Gunicorn)
□ 整体测试与修复
```

---

## 十四、部署说明

### 14.1 开发环境启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入实际配置

# 3. 初始化数据库
flask db init
flask db migrate -m "initial"
flask db upgrade

# 4. 初始化数据
flask shell
>>> from app.utils.init_db import init_data
>>> init_data()
>>> exit()

# 5. 启动应用
python run.py
```

### 14.2 生产环境

```bash
# 使用 Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app('production')"
```

### 14.3 访问入口

```
Web 管理端: http://localhost:5000/
H5 移动端: http://localhost:5000/h5/
API 文档:  http://localhost:5000/api/v1/
```

---

## 十五、模板数据示例

以下为一个**食品安全日常监督检查模板**的树形结构示例，用于理解模板设计和测试：

```json
{
  "template": {
    "name": "食品安全日常监督检查表",
    "industry": "食品安全",
    "scoring_mode": "none"
  },
  "tree": [
    {
      "name": "一、许可情况",
      "node_type": "category",
      "children": [
        {
          "name": "1.1 营业执照是否在有效期内",
          "node_type": "item",
          "check_type": "radio",
          "radio_options": [
            {"label": "合格", "value": "pass"},
            {"label": "不合格", "value": "fail"},
            {"label": "不适用", "value": "na"}
          ],
          "legal_basis": "《食品安全法》第三十五条",
          "key_points": "1. 查看营业执照原件\n2. 核对有效期\n3. 核对经营范围",
          "allow_attachment": true,
          "ai_enabled": true
        },
        {
          "name": "1.2 食品经营许可证是否在有效期内",
          "node_type": "item",
          "check_type": "radio",
          "radio_options": [
            {"label": "合格", "value": "pass"},
            {"label": "不合格", "value": "fail"}
          ],
          "legal_basis": "《食品安全法》第三十五条\n《食品经营许可管理办法》",
          "standard_basis": "许可证号应与实际经营主体一致",
          "key_points": "1. 查看许可证原件\n2. 核对许可范围与实际经营是否一致\n3. 检查许可证是否悬挂在显著位置"
        }
      ]
    },
    {
      "name": "二、环境卫生",
      "node_type": "category",
      "children": [
        {
          "name": "2.1 经营场所环境卫生",
          "node_type": "item",
          "check_type": "score",
          "max_score": 10,
          "min_score": 0,
          "score_step": 1,
          "key_points": "1. 地面是否清洁\n2. 墙壁是否有污渍\n3. 是否有防鼠防虫措施",
          "allow_attachment": true,
          "attachment_required": true
        },
        {
          "name": "2.2 食品加工区温度",
          "node_type": "item",
          "check_type": "numeric",
          "numeric_min": -5,
          "numeric_max": 40,
          "numeric_unit": "℃",
          "standard_basis": "GB 14881-2013《食品安全国家标准 食品生产通用卫生规范》",
          "key_points": "使用温度计现场测量，记录实际温度值"
        }
      ]
    },
    {
      "name": "三、现场检查总体评价",
      "node_type": "category",
      "children": [
        {
          "name": "3.1 总体情况描述",
          "node_type": "item",
          "check_type": "text",
          "text_placeholder": "请描述现场检查的总体情况...",
          "text_min_length": 20,
          "ai_enabled": true
        }
      ]
    }
  ]
}
```

---

## 十六、安全注意事项

1. **密码**: 使用 `werkzeug.security.generate_password_hash` 加密存储，禁止明文
2. **JWT**: 设置合理过期时间，密钥保存在环境变量中
3. **SQL 注入**: 使用 ORM 参数化查询，避免拼接 SQL
4. **XSS**: Jinja2 默认转义，API 输入做过滤
5. **文件上传**: 校验文件类型和大小，存储路径避免目录穿越
6. **CSRF**: Web 端表单使用 Flask-WTF 的 CSRF 保护
7. **数据库密码**: 通过环境变量注入，不硬编码到代码中

---

## 十七、扩展预留

以下功能在 MVP 中不实现，但数据库和代码结构已预留扩展空间：

1. **检查报告导出** (Word/PDF): 基于模板和检查结果自动生成报告
2. **多专家协作**: 多人同时检查同一企业
3. **整改跟踪**: 问题发现 → 下发整改 → 企业反馈 → 复查验证
4. **数据分析**: 按行业/地区/时间维度的检查数据统计分析
5. **消息通知**: 检查任务下发通知、整改到期提醒
6. **电子签名**: 检查完成后的电子签名确认
7. **离线模式**: H5 端支持离线检查，联网后同步
8. **企业自查**: 企业端自查功能
9. **API开放平台**: 对接第三方系统

---

> **本指南用于指导 AI Agent 进行代码开发。开发时请严格遵循上述数据库设计、目录结构、路由规划和业务逻辑。如有疑问请参照本文档中的代码示例和设计说明。**