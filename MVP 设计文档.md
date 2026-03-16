# 专家现场工作辅助系统 - MVP 设计文档

## 一、MVP 目标

**最小可用产品（Minimum Viable Product）**：实现最核心的现场检查功能，去掉复杂的任务管理流程。

### 核心流程
```
Web 管理端：创建检查模板
    ↓
H5 APP 端：选择模板 → 执行检查 → 提交记录
    ↓
Web 管理端：查看所有检查记录
```

## 二、功能范围

### ✅ MVP 包含的功能

| 模块 | 功能 | 说明 |
|------|------|------|
| **Web 管理端** | 模板管理 | 创建、编辑、删除检查模板，支持层级结构 |
| **Web 管理端** | 检查记录查看 | 查看所有现场检查提交的记录 |
| **Web 管理端** | 企业管理 | 管理被检查企业基础信息 |
| **H5 APP** | 模板选择 | 选择已发布的检查模板 |
| **H5 APP** | 检查执行 | 根据模板逐项检查、拍照上传 |
| **H5 APP** | 记录提交 | 提交检查结果 |
| **后端 API** | 模板 API | 模板 CRUD、项目 CRUD |
| **后端 API** | 记录 API | 检查记录的创建、查询 |
| **后端 API** | 企业 API | 企业信息管理 |
| **后端 API** | 媒体 API | 照片上传 |

### ❌ MVP 移除的功能

| 模块 | 功能 | 移除原因 |
|------|------|----------|
| 任务管理 | 任务创建、分配、跟踪 | 简化流程，直接检查 |
| 任务管理 | 任务状态管理 | 不需要复杂的工作流 |
| LLM 智能辅助 | 检查建议、法规依据 | 后续迭代添加 |
| 知识库管理 | 政策法规、审查细则 | 后续迭代添加 |
| 数据分析 | 操作审计、LLM 日志 | 后续迭代添加 |

## 三、数据库模型

### 核心模型（保留）

```sql
-- 检查模板
inspection_templates
├── id (UUID)
├── name (VARCHAR) - 模板名称
├── code (VARCHAR) - 模板编码
├── description (TEXT) - 描述
├── category (VARCHAR) - 类别
├── version (VARCHAR) - 版本号
├── is_published (BOOLEAN) - 是否发布
├── created_by (UUID) - 创建人
└── created_at, updated_at

-- 模板检查项
template_items
├── id (UUID)
├── template_id (UUID) - 所属模板
├── parent_id (UUID) - 父节点（支持层级）
├── title (VARCHAR) - 检查项标题
├── description (TEXT) - 描述
├── check_method (TEXT) - 检查方法
├── legal_basis (TEXT) - 法律依据
├── standard_ref (VARCHAR) - 标准依据
├── result_type (VARCHAR) - 结论类型：pass_fail/numeric/text
├── result_options (JSON) - 结论选项
├── min_value, max_value (NUMERIC) - 数值范围
├── unit (VARCHAR) - 单位
├── is_required (BOOLEAN) - 是否必填
├── risk_level (VARCHAR) - 风险等级
├── sort_order (INT) - 排序
├── is_category (BOOLEAN) - 是否为分类节点
└── created_by, created_at, updated_at

-- 企业
enterprises
├── id (UUID)
├── name (VARCHAR) - 企业名称
├── code (VARCHAR) - 统一社会信用代码
├── address (VARCHAR) - 地址
├── contact_person (VARCHAR) - 联系人
├── contact_phone (VARCHAR) - 联系电话
├── industry (VARCHAR) - 行业
├── scale (VARCHAR) - 规模
└── created_at, updated_at

-- 检查记录（简化版，去掉任务关联）
inspection_records
├── id (UUID)
├── template_id (UUID) - 使用的模板
├── enterprise_id (UUID) - 被检查企业
├── inspector_id (UUID) - 检查员
├── inspection_date (TIMESTAMP) - 检查时间
├── status (VARCHAR) - 状态：draft/submitted
├── overall_result (VARCHAR) - 总体结论
├── remarks (TEXT) - 备注
└── created_at, updated_at

-- 检查项记录
inspection_record_items
├── id (UUID)
├── record_id (UUID) - 所属检查记录
├── template_item_id (UUID) - 模板检查项
├── result (VARCHAR) - 检查结果：pass/fail
├── result_value (VARCHAR) - 数值结果
├── result_text (TEXT) - 文字结论
├── inspector_note (TEXT) - 检查员备注
├── photos (JSON) - 照片 URLs
└── recorded_at

-- 媒体文件
media_files
├── id (UUID)
├── record_id (UUID) - 关联记录
├── file_url (VARCHAR) - 文件 URL
├── file_type (VARCHAR) - 文件类型
├── uploaded_by (UUID) - 上传人
└── uploaded_at

-- 用户
users
├── id (UUID)
├── username (VARCHAR)
├── password_hash (VARCHAR)
├── real_name (VARCHAR)
├── role (VARCHAR) - admin/expert
└── created_at
```

### 简化说明

**移除的模型**：
- `inspection_tasks` - 检查任务表（MVP 不需要任务概念）
- `task_item_records` - 任务检查项记录（合并到 inspection_record_items）

## 四、API 设计

### 模板管理 API

```
GET    /api/templates              - 获取模板列表
POST   /api/templates              - 创建模板
GET    /api/templates/:id          - 获取模板详情（含检查项）
PUT    /api/templates/:id          - 更新模板
DELETE /api/templates/:id          - 删除模板
POST   /api/templates/:id/publish  - 发布模板

POST   /api/templates/:id/items    - 添加检查项
PUT    /api/templates/items/:id    - 更新检查项
DELETE /api/templates/items/:id    - 删除检查项
```

### 检查记录 API

```
GET    /api/records                - 获取检查记录列表
POST   /api/records                - 创建检查记录
GET    /api/records/:id            - 获取记录详情
PUT    /api/records/:id            - 更新记录
POST   /api/records/:id/submit     - 提交记录

GET    /api/records/:id/items      - 获取记录的检查项
POST   /api/records/:id/items      - 添加/更新检查项结果
```

### 企业管理 API

```
GET    /api/enterprises            - 获取企业列表
POST   /api/enterprises            - 创建企业
GET    /api/enterprises/:id        - 获取企业详情
PUT    /api/enterprises/:id        - 更新企业
DELETE /api/enterprises/:id        - 删除企业
```

### 媒体管理 API

```
POST   /api/media/upload           - 上传文件
GET    /api/media/:id              - 获取文件信息
DELETE /api/media/:id              - 删除文件
```

### 认证 API

```
POST   /api/auth/login             - 登录
POST   /api/auth/logout            - 登出
GET    /api/auth/me                - 获取当前用户
```

## 五、前端页面设计

### Web 管理端

```
/dashboard          - 仪表盘（可选）
/templates          - 模板管理
/templates/:id      - 模板详情/编辑
/records            - 检查记录列表
/records/:id        - 记录详情
/enterprises        - 企业管理
/login              - 登录
```

### H5 APP

```
/login              - 登录
/home               - 首页（模板选择）
/inspection/:id     - 检查执行
/records            - 我的检查记录
/profile            - 个人中心
```

## 六、实施计划

### 阶段 1：后端 API 调整（优先级：高）

1. **创建新的检查记录模型**
   - [ ] 创建 `inspection_records` 表（去掉任务关联）
   - [ ] 创建 `inspection_record_items` 表
   - [ ] 迁移现有数据（如有）

2. **实现记录 API**
   - [ ] `GET /api/records` - 获取记录列表
   - [ ] `POST /api/records` - 创建记录
   - [ ] `GET /api/records/:id` - 获取详情
   - [ ] `POST /api/records/:id/submit` - 提交记录
   - [ ] `POST /api/records/:id/items` - 添加检查项结果

3. **简化任务 API（可选保留）**
   - 暂时保留任务 API 用于向后兼容
   - 新代码使用记录 API

### 阶段 2：Web 管理端（优先级：高）

1. **模板管理页面优化**
   - [x] 已有 - 模板 CRUD
   - [x] 已有 - 检查项层级管理
   - [ ] 优化用户体验

2. **检查记录页面**
   - [ ] 新建记录列表页
   - [ ] 记录详情页（查看检查结果、照片）
   - [ ] 筛选功能（按企业、时间、检查员）

3. **企业管理页面**
   - [x] 已有 - 企业 CRUD
   - [ ] 企业资质、产品、设备管理（可选）

### 阶段 3：H5 APP（优先级：高）

1. **首页改造**
   - [ ] 模板选择界面
   - [ ] 选择企业（或手动输入）
   - [ ] 开始检查

2. **检查执行页面**
   - [x] 已有 - 检查项展示
   - [x] 已有 - 结果输入
   - [x] 已有 - 拍照上传
   - [ ] 优化体验

3. **记录查看**
   - [ ] 我的检查记录列表
   - [ ] 记录详情

### 阶段 4：测试与优化（优先级：中）

- [ ] 端到端测试
- [ ] 性能优化
- [ ] UI/UX优化

## 七、技术实现细节

### 数据库迁移

```sql
-- 创建检查记录表
CREATE TABLE inspection_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID REFERENCES inspection_templates(id),
    enterprise_id UUID REFERENCES enterprises(id),
    inspector_id UUID REFERENCES users(id),
    inspection_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'draft',
    overall_result VARCHAR(20),
    remarks TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建检查项记录表
CREATE TABLE inspection_record_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id UUID REFERENCES inspection_records(id) ON DELETE CASCADE,
    template_item_id UUID REFERENCES template_items(id),
    result VARCHAR(20),
    result_value VARCHAR(50),
    result_text TEXT,
    inspector_note TEXT,
    photos JSONB,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引
CREATE INDEX idx_records_template ON inspection_records(template_id);
CREATE INDEX idx_records_enterprise ON inspection_records(enterprise_id);
CREATE INDEX idx_records_inspector ON inspection_records(inspector_id);
CREATE INDEX idx_records_date ON inspection_records(inspection_date);
CREATE INDEX idx_record_items_record ON inspection_record_items(record_id);
```

### 后端 Schema 定义

```python
# schemas/record.py
class InspectionRecordCreate(BaseModel):
    template_id: UUID
    enterprise_id: Optional[UUID] = None
    enterprise_name: Optional[str] = None  # 手动输入时使用
    enterprise_address: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    inspection_date: Optional[datetime] = None
    remarks: Optional[str] = None

class InspectionRecordItemCreate(BaseModel):
    template_item_id: UUID
    result: Optional[str] = None
    result_value: Optional[str] = None
    result_text: Optional[str] = None
    inspector_note: Optional[str] = None
    photos: Optional[List[str]] = None
```

## 八、MVP 验收标准

### 功能完整性

- [ ] Web 端可以创建和编辑检查模板
- [ ] Web 端可以查看检查记录
- [ ] H5 端可以选择模板
- [ ] H5 端可以执行检查并提交
- [ ] 照片可以正常上传和查看
- [ ] 数据正确保存到数据库

### 性能要求

- [ ] 页面加载时间 < 3 秒
- [ ] API 响应时间 < 1 秒
- [ ] 照片上传支持断点续传

### 用户体验

- [ ] 界面简洁直观
- [ ] 操作流程顺畅
- [ ] 错误提示清晰

## 九、后续迭代规划

### v1.1 - LLM 智能辅助
- 检查建议生成
- 法规依据查询
- 智能判定

### v1.2 - 知识库管理
- 政策法规库
- 审查细则
- 案例库

### v1.3 - 任务管理（可选）
- 任务分配
- 进度跟踪
- 统计分析

### v2.0 - 数据分析
- 仪表盘
- 趋势分析
- 导出报告
