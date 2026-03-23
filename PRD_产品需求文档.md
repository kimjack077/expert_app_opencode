# 专家现场工作辅助系统 (EFIS) 产品需求文档 (PRD)

## 1. 产品概述

### 1.1 产品名称
专家现场工作辅助系统

### 1.2 产品定位
面向政府监管部门、认证机构、第三方检测机构的专业现场检查辅助系统，通过AI技术赋能检查员，提高现场检查效率和规范性。

### 1.3 目标用户
| 用户角色 | 职责描述 |
|---------|---------|
| **super_admin** (超级管理员) | 系统全局配置、用户管理、数据维护 |
| **admin** (管理员) | 模板管理、任务分配、数据分析 |
| **expert** (检查专家) | 执行现场检查、填写检查记录、使用AI辅助 |
| **auditor** (审核员) | 查看检查记录、审核检查结果 |

### 1.4 核心价值
- **标准化检查流程**：通过模板化管理确保检查规范
- **AI智能辅助**：实时生成检查结论、法规依据、最终判定
- **移动端优先**：支持H5移动端现场操作
- **数据可追溯**：完整的审计日志和检查记录

---

## 2. 系统架构

### 2.1 技术架构
```
┌─────────────────────────────────────────────────────────────┐
│                      前端应用层                              │
├─────────────────┬─────────────────┬─────────────────────────┤
│  Web管理后台     │   H5移动端      │   移动APP (可选)        │
│  React 18       │   Vue 3         │   React Native         │
│  Ant Design     │   Vant 4        │                        │
└────────┬────────┴────────┬────────┴────────────┬───────────┘
         │                 │                      │
         └─────────────────┼──────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    后端服务层 (FastAPI)                       │
├─────────────────────────────────────────────────────────────┤
│  认证模块 │ 模板管理 │ 任务管理 │ 记录管理 │ AI服务 │ Agent  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                      数据层                                  │
├─────────────────────────┬───────────────────────────────────┤
│     PostgreSQL          │         LLM服务                   │
│     (主数据库)           │    (OpenAI兼容接口)               │
└─────────────────────────┴───────────────────────────────────┘
```

### 2.2 部署架构
- **后端服务**：FastAPI + Uvicorn，端口8000
- **Web管理端**：`/` 路径
- **H5移动端**：`/h5/` 路径
- **API接口**：`/api/` 路径
- **文件服务**：`/uploads/` 静态文件

---

## 3. 功能模块详解

### 3.1 用户认证与权限管理

#### 3.1.1 用户登录
| 功能项 | 描述 |
|-------|------|
| 登录方式 | 用户名+密码 |
| 认证机制 | JWT Token (access_token 8小时 + refresh_token 30天) |
| Token刷新 | 自动刷新机制，401响应时自动刷新 |
| 安全措施 | 密码bcrypt加密、登录日志记录 |

**API接口**：
- `POST /api/auth/login` - 用户登录
- `POST /api/auth/logout` - 用户登出
- `POST /api/auth/refresh` - 刷新Token
- `GET /api/auth/me` - 获取当前用户信息
- `PUT /api/auth/me/password` - 修改密码

#### 3.1.2 用户管理
| 功能项 | 描述 |
|-------|------|
| 用户列表 | 分页查询、关键词搜索、角色筛选 |
| 用户操作 | 新增、编辑、启用/禁用、删除 |
| 角色分配 | 支持四种角色：super_admin/admin/expert/auditor |
| 行业关联 | 用户可关联所属行业 |

**数据模型**：
```
User: id, username, email, phone, hashed_password, full_name, 
      role, org_id, industry_id, is_active, last_login_at
```

#### 3.1.3 组织机构管理
- 树形组织结构
- 用户归属组织

### 3.2 行业分类管理

#### 3.2.1 行业分类维护
| 功能项 | 描述 |
|-------|------|
| 分类结构 | 多级树形结构 |
| 分类属性 | 名称、编码、图标、排序、状态 |
| 关联关系 | 企业归属行业、模板关联行业、用户所属行业 |

**数据模型**：
```
Industry: id, name, code, parent_id, icon, sort_order, is_active
```

### 3.3 企业管理

#### 3.3.1 企业信息管理
| 功能项 | 描述 |
|-------|------|
| 企业基本信息 | 名称、统一社会信用代码、地址、法人、联系方式 |
| 企业属性 | 行业分类、企业类型、经济类型、风险等级 |
| 地理位置 | 经纬度、区县、街道 |

#### 3.3.2 企业扩展信息
| 模块 | 字段 |
|------|------|
| **企业资质** | 资质类型、证书编号、产品名称、有效期、发证机关 |
| **企业产品** | 产品名称、类别、规格、年产量、认证状态 |
| **企业设备** | 设备名称、型号、厂家、购置日期、状态 |
| **企业仪器** | 仪器名称、型号、编号、测量范围、检定周期 |
| **企业人员** | 姓名、职务、证书、有效期 |
| **整改记录** | 问题描述、整改要求、期限、状态 |

**数据模型**：
```
Enterprise → EnterpriseQualification (1:N)
           → EnterpriseProduct (1:N)
           → EnterpriseEquipment (1:N)
           → EnterpriseInstrument (1:N)
           → EnterprisePersonnel (1:N)
           → RectificationRecord (1:N)
```

### 3.4 检查模板管理

#### 3.4.1 模板基本信息
| 字段 | 描述 |
|------|------|
| 模板名称 | 如"食品安全检查模板" |
| 模板编码 | 唯一标识 |
| 模板类别 | 食品安全、安全生产等 |
| 关联行业 | 模板适用的行业分类 |
| 版本管理 | 版本号、发布状态 |
| 可见范围 | 公共模板(所有专家可见) / 个人模板(仅创建者可见) |

#### 3.4.2 检查项配置
**检查项结构**：支持多级树形结构（分类节点 + 检查项）

**检查项属性**：
| 属性 | 描述 |
|------|------|
| 标题 | 检查项目名称 |
| 描述 | 检查项目详细说明 |
| 检查方法 | 具体检查方法指导 |
| 法律依据 | 相关法规条款 |
| 标准参考 | 相关标准编号 |

**检查类型配置**：
| 类型 | 说明 | 配置项 |
|------|------|--------|
| `radio` | 单选判定 | 结果选项(合格/不合格/不适用) |
| `multi_check` | 多选判定 | 多选选项列表 |
| `score` | 打分类型 | 最大分、步长、合格分数线、权重 |
| `numeric` | 数值类型 | 最小值、最大值、单位 |
| `text` | 文本描述 | 自由文本输入 |

**AI配置**：
| 属性 | 描述 |
|------|------|
| use_ai | 是否启用AI辅助 |
| ai_prompt_template | 自定义AI提示词模板 |
| risk_level | 风险等级 |

**附件配置**：
| 属性 | 描述 |
|------|------|
| allow_attachment | 是否允许附件 |
| attachment_required | 附件是否必须 |

#### 3.4.3 AI辅助模板提取
- 支持从PDF/Word/Excel文档自动提取检查项
- 自动识别文档结构生成模板
- 支持手动调整和补充

**API接口**：
- `POST /api/ai-extract/extract` - AI提取模板内容

### 3.5 检查任务管理

#### 3.5.1 任务创建与分配
| 功能项 | 描述 |
|-------|------|
| 任务创建 | 选择企业、选择模板、设置计划时间 |
| 任务分配 | 指定检查员 |
| 任务状态 | pending(待执行) → in_progress(进行中) → completed(已完成) |

#### 3.5.2 任务信息
| 字段 | 描述 |
|------|------|
| 任务编号 | 自动生成唯一编号 |
| 任务标题 | 任务名称 |
| 关联模板 | 使用的检查模板 |
| 被检查对象 | 企业名称、地址、联系人 |
| 计划时间 | 预计检查日期 |
| 实际时间 | 开始时间、完成时间 |

**数据模型**：
```
InspectionTask → TaskItemRecord (1:N，每个检查项的记录)
TaskItemRecord → MediaFile (1:N，附件照片)
```

### 3.6 现场检查执行 (H5移动端核心功能)

#### 3.6.1 检查流程
```
选择企业 → 选择模板 → 逐项检查 → AI辅助 → 生成报告
```

#### 3.6.2 检查执行界面
| 功能 | 描述 |
|------|------|
| 检查项列表 | 树形结构展示所有检查项 |
| 进度显示 | 已检查/总数、合格/不合格统计 |
| 快速定位 | 按状态筛选、搜索检查项 |

#### 3.6.3 单项检查
| 功能 | 描述 |
|------|------|
| 结果录入 | 根据检查类型(单选/打分/数值/文本)录入结果 |
| 问题描述 | 不合格项填写问题描述 |
| 拍照取证 | 支持现场拍照、相册选择 |
| AI建议 | 一键生成检查结论建议 |
| 法规依据 | 查看相关法规条款 |

#### 3.6.4 AI辅助功能
**LLM服务**：
| 功能 | 描述 |
|------|------|
| 检查建议生成 | 根据检查项和结果生成专业结论 |
| 法规依据查询 | 提供相关法规标准引用 |
| 最终判定生成 | 汇总所有检查项生成总体评价 |

**Agent助手**：
| 工具 | 功能 |
|------|------|
| list_check_items | 列出所有检查项及状态 |
| get_check_item_details | 获取检查项详情 |
| get_inspection_summary | 获取检查汇总 |
| generate_final_verdict | 生成最终判定建议 |

**API接口**：
- `POST /api/llm/suggestion` - 生成检查建议
- `POST /api/llm/suggestion/stream` - 流式生成检查建议
- `POST /api/llm/basis` - 获取法规依据
- `POST /api/llm/final-judgment` - 生成最终判定
- `POST /api/agent/chat/stream` - Agent对话(流式)

#### 3.6.5 离线支持
- 本地存储检查数据
- 照片上传队列
- 断网续传机制

### 3.7 检查记录管理

#### 3.7.1 记录结构
```
InspectionRecord (检查记录主表)
├── template_snapshot (模板快照，防止模板变更影响历史记录)
├── enterprise_id / enterprise_name (被检查企业)
├── inspector_id (检查员)
├── status (draft/submitted)
├── overall_result (总体结论)
└── items[] (检查记录项列表)
    ├── template_item_id (关联模板项)
    ├── result (检查结果)
    ├── result_value (数值结果)
    ├── result_text (文字结论)
    ├── llm_suggestion (AI建议)
    ├── llm_basis (AI依据)
    └── media_files[] (附件照片)
```

#### 3.7.2 记录操作
| 操作 | 描述 |
|------|------|
| 保存草稿 | 检查过程中随时保存 |
| 提交记录 | 完成检查后提交 |
| 查看详情 | 查看完整检查记录 |
| 导出报告 | 生成PDF检查报告 |

### 3.8 知识库管理

#### 3.8.1 知识分类
```
KnowledgeCategory (知识分类)
├── name (分类名称)
├── code (分类编码)
├── parent_id (父分类)
└── documents[] (文档列表)
```

#### 3.8.2 知识文档
| 字段 | 描述 |
|------|------|
| 标题 | 文档标题 |
| 文档类型 | 法规/标准/指南/其他 |
| 文号 | 文件编号 |
| 内容 | 文档正文 |
| 关键词 | 检索关键词 |
| 发布机关 | 发文单位 |
| 有效期 | 生效日期、失效日期 |
| 附件 | 原文件下载 |

#### 3.8.3 检查指南
```
InspectionGuideline (检查指南)
├── name (指南名称)
├── product_category (产品类别)
├── content (指南内容)
├── legal_basis (法律依据)
└── version (版本号)
```

### 3.9 数据分析与统计

#### 3.9.1 仪表盘
| 指标 | 描述 |
|------|------|
| 检查任务统计 | 待执行/进行中/已完成数量 |
| 检查记录统计 | 今日/本周/本月检查数量 |
| 合格率趋势 | 按时间段统计合格率 |
| 企业风险分布 | 按风险等级统计企业数量 |

#### 3.9.2 审计日志
- 所有写操作自动记录
- 记录操作人、操作时间、操作内容
- 支持日志查询和导出

### 3.10 文件管理

#### 3.10.1 文件上传
| 功能 | 描述 |
|------|------|
| 支持格式 | 图片(jpg/png)、文档(pdf/docx/xlsx) |
| 存储方式 | 本地文件系统 |
| 文件命名 | UUID命名，防止冲突 |
| 图片处理 | 自动压缩、尺寸调整 |

#### 3.10.2 文件关联
- 关联检查记录
- 关联检查项
- 关联知识文档

---

## 4. 用户界面设计

### 4.1 Web管理端页面

| 路由 | 页面 | 功能描述 |
|------|------|---------|
| `/login` | 登录页 | 用户登录 |
| `/dashboard` | 仪表盘 | 数据概览、快捷入口 |
| `/templates` | 模板列表 | 模板管理、新建模板 |
| `/templates/:id` | 模板编辑 | 树形编辑检查项 |
| `/enterprises` | 企业列表 | 企业信息管理 |
| `/tasks` | 任务列表 | 任务管理、任务分配 |
| `/tasks/:id` | 任务详情 | 任务信息、执行进度 |
| `/inspection/new` | 新建检查 | 快速发起检查 |
| `/inspection/:id` | 检查执行 | 检查项填写 |
| `/record/:id` | 记录详情 | 检查记录查看 |
| `/records` | 记录列表 | 历史记录查询 |
| `/knowledge` | 知识库 | 法规标准管理 |
| `/analytics` | 数据分析 | 统计报表 |
| `/users` | 用户管理 | 用户账号管理 |
| `/industries` | 行业管理 | 行业分类维护 |

### 4.2 H5移动端页面

| 路由 | 页面 | 功能描述 |
|------|------|---------|
| `/login` | 登录页 | 移动端登录 |
| `/home` | 首页 | 快捷入口、待办任务 |
| `/select-enterprise` | 选择企业 | 搜索选择被检查企业 |
| `/select-template` | 选择模板 | 选择检查模板 |
| `/tasks` | 任务列表 | 我的检查任务 |
| `/task/:id` | 任务详情 | 任务信息查看 |
| `/inspection/:id` | 检查执行 | 检查项列表、进度 |
| `/inspection/:id/item/:itemId` | 单项检查 | 填写检查结果 |
| `/records` | 记录列表 | 历史检查记录 |
| `/record/:id` | 记录详情 | 查看检查结果 |
| `/record/:id/report` | 报告预览 | 检查报告预览 |
| `/profile` | 个人中心 | 个人信息设置 |
| `/statistics` | 统计 | 个人检查统计 |
| `/settings` | 设置 | 系统设置 |
| `/about` | 关于 | 系统信息 |

---

## 5. API接口设计

### 5.1 统一响应格式
```json
{
  "code": 200,
  "message": "success",
  "data": {},
  "timestamp": "2026-03-16T10:00:00Z"
}
```

### 5.2 API模块列表

| 模块 | 前缀 | 描述 |
|------|------|------|
| 认证 | `/api/auth` | 登录、登出、Token刷新 |
| 用户 | `/api/users` | 用户CRUD |
| 行业 | `/api/industries` | 行业分类管理 |
| 企业 | `/api/enterprises` | 企业信息管理 |
| 模板 | `/api/templates` | 检查模板管理 |
| 任务 | `/api/tasks` | 检查任务管理 |
| 记录 | `/api/records` | 检查记录管理 |
| 文件 | `/api/media` | 文件上传下载 |
| LLM | `/api/llm` | AI建议服务 |
| Agent | `/api/agent` | AI助手对话 |
| AI提取 | `/api/ai-extract` | AI辅助模板提取 |
| 知识库 | `/api/knowledge` | 知识文档管理 |
| 分析 | `/api/analytics` | 数据统计分析 |

---

## 6. 非功能性需求

### 6.1 性能需求
| 指标 | 要求 |
|------|------|
| 响应时间 | 普通接口 < 500ms |
| AI接口 | 流式响应，首字 < 2s |
| 并发用户 | 支持100+并发用户 |
| 数据量 | 支持百万级记录 |

### 6.2 安全需求
| 需求 | 措施 |
|------|------|
| 密码安全 | bcrypt加密存储 |
| 认证机制 | JWT Token认证 |
| 权限控制 | 基于角色的访问控制(RBAC) |
| 操作审计 | 全量操作日志记录 |
| SQL注入防护 | SQLAlchemy参数化查询 |
| XSS防护 | 输入输出转义 |

### 6.3 可用性需求
| 需求 | 描述 |
|------|------|
| 系统可用性 | > 99.5% |
| 数据备份 | 定期备份，支持恢复 |
| 错误提示 | 友好的错误信息 |
| 离线支持 | H5端支持离线操作 |

### 6.4 兼容性需求
| 端 | 支持环境 |
|------|---------|
| Web管理端 | Chrome、Firefox、Edge最新版本 |
| H5移动端 | iOS Safari、Android Chrome |
| 屏幕适配 | 响应式设计，适配不同屏幕 |

---

## 7. 数据库设计概要

### 7.1 核心数据表

| 表名 | 说明 | 主要字段 |
|------|------|----------|
| `users` | 用户表 | id, username, email, role, is_active |
| `organizations` | 组织机构表 | id, name, code |
| `industries` | 行业分类表 | id, name, code, parent_id |
| `enterprises` | 企业表 | id, name, credit_code, industry_id |
| `enterprise_qualifications` | 企业资质表 | id, enterprise_id, qual_type, cert_no |
| `enterprise_products` | 企业产品表 | id, enterprise_id, name, category |
| `enterprise_equipment` | 企业设备表 | id, enterprise_id, name, model |
| `enterprise_instruments` | 企业仪器表 | id, enterprise_id, name, model |
| `enterprise_personnel` | 企业人员表 | id, enterprise_id, name, position |
| `rectification_records` | 整改记录表 | id, enterprise_id, issue_desc |
| `inspection_templates` | 检查模板表 | id, name, code, category, is_published |
| `template_items` | 检查项表 | id, template_id, parent_id, title, check_type |
| `inspection_tasks` | 检查任务表 | id, task_no, template_id, assigned_to, status |
| `task_item_records` | 任务检查记录表 | id, task_id, template_item_id, result |
| `inspection_records` | 检查记录表 | id, template_id, enterprise_id, status |
| `inspection_record_items` | 检查记录项表 | id, record_id, template_item_id, result |
| `media_files` | 媒体文件表 | id, file_path, file_type, record_id |
| `knowledge_categories` | 知识分类表 | id, name, code, parent_id |
| `knowledge_documents` | 知识文档表 | id, category_id, title, content |
| `inspection_guidelines` | 检查指南表 | id, name, product_category, content |
| `audit_logs` | 审计日志表 | id, user_id, action, resource |
| `llm_call_logs` | LLM调用日志表 | id, user_id, prompt, response, duration_ms |

### 7.2 关键关系
```
InspectionTemplate → TemplateItem (1:N, 树形结构)
InspectionTask → TaskItemRecord (1:N)
TaskItemRecord → TemplateItem (N:1)
TaskItemRecord → MediaFile (1:N)
InspectionRecord → InspectionRecordItem (1:N)
InspectionRecord → TemplateItem (通过template_snapshot)
Enterprise → EnterpriseQualification/Product/Equipment/Instrument/Personnel (1:N)
```

---

## 8. 版本规划

### 8.1 MVP版本 (v1.0)
- ✅ 用户认证与权限管理
- ✅ 检查模板管理
- ✅ 企业信息管理
- ✅ 检查任务管理
- ✅ 现场检查执行(H5)
- ✅ AI检查建议
- ✅ 检查记录管理
- ✅ 知识库管理

### 8.2 后续规划
- 📋 移动APP原生版本
- 📋 语音输入支持
- 📋 图像识别辅助
- 📋 数据大屏展示
- 📋 多租户支持
- 📋 与外部系统对接

---

## 9. 附录

### 9.1 技术栈清单

| 层级 | 技术 | 版本 |
|------|------|------|
| 后端框架 | FastAPI | Python 3.11+ |
| 数据库 | PostgreSQL | 14+ |
| ORM | SQLAlchemy | 2.0+ (Async) |
| 数据库迁移 | Alembic | - |
| 认证 | python-jose | JWT |
| 密码加密 | passlib + bcrypt | - |
| LLM客户端 | openai | SDK |
| 文档处理 | PyMuPDF, python-docx, openpyxl | - |
| 图片处理 | Pillow | - |
| Web前端 | React 18 + TypeScript + Vite | - |
| UI组件库 | Ant Design | - |
| 状态管理 | Zustand | - |
| H5前端 | Vue 3 + TypeScript + Vite | - |
| H5组件库 | Vant 4 | - |
| 路由 | React Router / Vue Router | - |

### 9.2 环境配置

| 配置项 | 说明 |
|--------|------|
| `VITE_API_URL` | 后端API地址 |
| `PG_HOST/PORT/DB/USER/PASSWORD` | PostgreSQL连接 |
| `LLM_BASE_URL/MODEL/API_KEY` | LLM服务配置 |
| `LLM_TIMEOUT` | LLM请求超时(默认180s) |
| `UPLOAD_DIR` | 文件上传目录 |

---

*文档版本：v1.0*  
*最后更新：2026-03-16*
