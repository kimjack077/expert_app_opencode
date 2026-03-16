# Expert App - 专家现场工作辅助系统

一个辅助专家现场工作的多端应用系统，支持检查、审查、监管等工作流程管理。

## 项目简介

本系统为专家现场工作提供信息化支持，主要功能包括：
- **现场检查记录**：记录检查结果、审查意见、监管情况、现场照片等信息
- **智能辅助**：通过LLM获取检查建议和法规依据
- **模板管理**：管理员可自定义检查模板，按不同政策标准分解检查条目
- **企业信息管理**：管理被检查企业的基础信息、资质、产品、设备等
- **知识库管理**：管理政策法规、审查细则等文档
- **操作审计**：记录所有现场工作人员的操作行为，支持管理员查看分析

## 技术栈

### 后端
- Python 3.x
- FastAPI
- PostgreSQL
- SQLAlchemy + Alembic
- JWT认证

### 前端
- **Web管理后台**: React + Vite + TypeScript + Ant Design
- **移动APP**: React + Vite + TypeScript
- **H5应用**: Vue 3 + TypeScript + Vant
- **检查APP**: Flutter

## 项目结构

```
expert_app_opencode/
├── backend/           # 后端服务 (FastAPI)
│   ├── app/
│   │   ├── models/    # 数据库模型
│   │   ├── routers/   # API路由
│   │   ├── schemas/   # Pydantic模型
│   │   └── services/  # 业务逻辑
│   └── alembic/       # 数据库迁移
├── web-admin/         # Web管理后台
├── mobile-app/        # 移动端APP
├── h5-app/            # H5应用
└── inspection_app/    # Flutter检查APP
```

## 快速开始

### 环境要求
- Python 3.10+
- Node.js 18+
- PostgreSQL 14+

### 后端启动

```bash
cd backend

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境 (Windows)
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
copy .env.example .env
# 编辑 .env 文件配置数据库连接等信息

# 运行数据库迁移
alembic upgrade head

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端启动

```bash
# Web管理后台
cd web-admin
npm install
npm run dev

# 移动APP
cd mobile-app
npm install
npm run dev

# H5应用
cd h5-app
npm install
npm run dev
```

## 功能模块

### 后端API

#### 认证模块
- `POST /api/auth/login` - 用户登录
- `POST /api/auth/logout` - 用户登出
- `GET /api/auth/me` - 获取当前用户信息
- `PUT /api/auth/me/password` - 修改密码

#### 任务管理
- `GET /api/tasks/` - 获取任务列表
- `POST /api/tasks/` - 创建任务
- `GET /api/tasks/{id}` - 获取任务详情
- `POST /api/tasks/{id}/start` - 开始任务
- `POST /api/tasks/{id}/complete` - 完成任务
- `GET /api/tasks/{id}/records` - 获取任务记录
- `POST /api/tasks/{id}/records` - 创建检查记录

#### 模板管理
- `GET /api/templates/categories` - 获取标准分类
- `POST /api/templates/categories` - 创建分类
- `GET /api/templates/items` - 获取检查项
- `POST /api/templates/items` - 创建检查项
- `GET /api/templates/` - 获取模板列表
- `POST /api/templates/` - 创建模板
- `POST /api/templates/{id}/publish` - 发布模板

#### 企业管理
- `GET /api/enterprises/` - 获取企业列表
- `POST /api/enterprises/` - 创建企业
- `GET /api/enterprises/{id}` - 获取企业详情
- `PUT /api/enterprises/{id}` - 更新企业
- `DELETE /api/enterprises/{id}` - 删除企业
- `GET /api/enterprises/{id}/qualifications` - 获取资质信息
- `POST /api/enterprises/{id}/qualifications` - 创建资质
- `GET /api/enterprises/{id}/products` - 获取产品信息
- `POST /api/enterprises/{id}/products` - 创建产品
- `GET /api/enterprises/{id}/instruments` - 获取计量器具
- `POST /api/enterprises/{id}/instruments` - 创建计量器具
- `GET /api/enterprises/{id}/rectifications` - 获取整改记录
- `POST /api/enterprises/{id}/rectifications` - 创建整改记录

#### 知识库管理
- `GET /api/knowledge/categories` - 获取知识分类
- `POST /api/knowledge/categories` - 创建分类
- `GET /api/knowledge/documents` - 获取文档列表
- `POST /api/knowledge/documents` - 创建文档
- `GET /api/knowledge/documents/{id}` - 获取文档详情
- `PUT /api/knowledge/documents/{id}` - 更新文档
- `DELETE /api/knowledge/documents/{id}` - 删除文档
- `GET /api/knowledge/guidelines` - 获取审查细则
- `POST /api/knowledge/guidelines` - 创建审查细则

#### LLM智能辅助
- `POST /api/llm/suggestion` - 获取检查建议
- `POST /api/llm/basis` - 获取法规依据
- `GET /api/records/{record_id}/items/{item_id}/ai-stream` - 流式生成AI建议（SSE）

#### 媒体管理
- `POST /api/media/upload` - 上传文件
- `GET /api/media/task/{task_id}` - 获取任务媒体文件
- `DELETE /api/media/{id}` - 删除媒体文件

#### 数据分析
- `GET /api/analytics/dashboard` - 获取仪表盘数据
- `GET /api/analytics/audit-logs` - 获取审计日志
- `GET /api/analytics/llm-logs` - 获取LLM调用日志

### Web管理后台功能

- **仪表盘**：统计概览、任务进度、用户统计
- **企业管理**：企业信息、资质、产品、设备、整改记录管理
- **检查模板**：标准分类、检查项、模板管理
- **检查任务**：任务创建、分配、执行、完成
- **知识库**：政策法规、审查细则管理
- **数据分析**：操作审计、LLM调用分析

### H5应用功能

- **登录/注册**：支持用户名密码登录
- **任务列表**：查看分配的任务
- **任务执行**：现场检查、拍照上传、结果记录
- **快速检查**：无需任务的快速检查模式
- **个人中心**：个人信息、修改密码

## 数据库模型

### 核心模型
- **User**：用户（管理员、专家、检查员）
- **Organization**：组织机构
- **Enterprise**：企业信息
- **EnterpriseQualification**：企业资质
- **EnterpriseProduct**：企业产品
- **EnterpriseEquipment**：生产设备
- **EnterpriseInstrument**：计量器具
- **EnterprisePersonnel**：企业人员
- **RectificationRecord**：整改记录
- **InspectionTask**：检查任务
- **InspectionRecord**：检查记录
- **InspectionTemplate**：检查模板
- **CheckItem**：检查项
- **StandardCategory**：标准分类
- **KnowledgeCategory**：知识分类
- **KnowledgeDocument**：知识文档
- **InspectionGuideline**：审查细则
- **MediaFile**：媒体文件
- **AuditLog**：审计日志

## 配置

### 数据库配置 (.env)
```
DATABASE_URL=postgresql+asyncpg://username:password@host:port/dbname
```

### LLM配置 (.env)
```
LLM_BASE_URL=https://integrate.api.nvidia.com/v1
LLM_API_KEY=your_api_key
LLM_MODEL=deepseek-ai/deepseek-v3.2
```

### JWT配置 (.env)
```
SECRET_KEY=your_secret_key
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

## 开发规范

### 代码风格
- 后端：遵循 PEP 8 规范
- 前端：使用 ESLint + Prettier

### Git提交规范
```
feat: 新功能
fix: 修复bug
docs: 文档更新
style: 代码格式调整
refactor: 重构
test: 测试相关
chore: 构建/工具相关
```

## 测试

### 后端测试
```bash
cd backend
pytest
```

### 前端测试
```bash
cd web-admin
npm run test
```

## 部署

### Docker部署
```bash
docker-compose up -d
```

### 手动部署
1. 配置生产环境数据库
2. 配置环境变量
3. 运行数据库迁移
4. 启动后端服务
5. 构建并部署前端应用

## 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 更新日志

### v1.3.0 (2026-03-07)
- 新增检查结果统计汇总功能
  - H5端：完成检查后自动显示符合项、不符合项、不适用项统计
  - Web端：记录详情页显示检查结果统计卡片
  - AI生成最终判定自动包含统计信息
- 新增模板复制自定义名称功能
  - 复制模板时可自定义新模板名称
  - 修复复制模板时忽略用户输入名称的问题
- 修复 AI 生成最终判定时空值转换错误

### v1.2.0 (2026-03-07)
- 新增最终判定 AI 生成功能，自动总结所有检查项
- AI 自动识别判定结果（合格/基本合格/不合格）
- AI 生成总体评价填入判定说明
- 优化最终判定 prompt，简化输出格式
- 修复流式输出数据库会话问题

### v1.1.0 (2026-03-07)
- 新增 AI 流式输出功能，实时显示思考过程
- 新增认证审查检查模板
- 新增安全生产检查模板
- 修复模板项 is_category 字段查询问题
- 修复检查记录项创建逻辑
- 优化 LLM 提示词，生成更简洁的检查结论
- 修复 LLM 调用日志外键约束问题
- 改进企业管理页面，增加编辑功能

### v1.0.0 (2026-02-25)
- 初始版本发布
- 实现基础检查任务管理
- 实现模板管理功能
- 实现 LLM 智能辅助
- 实现企业信息管理
- 实现知识库管理
- 实现操作审计功能

## 许可证

MIT License

## 联系方式

如有问题或建议，欢迎提交 Issue 或 Pull Request。
