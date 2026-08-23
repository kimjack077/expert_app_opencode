# 易审通 (EasyAudit) - 认证审核与现场评审智能云平台

> **让每一次审核都变得简单高效** (Empowering Audit with Simplicity & Intelligence)

易审通（EasyAudit）用于认证审核、现场检查和整改闭环。审核员可通过 H5 端以文字、语音或照片提交证据；智审 Agent 生成多个候选条款草稿；人工确认后，记录、异常、不符合项、报告和资料包进入同一条正式审核数据链。

## 核心原则

- Agent 是统一交互入口，不新增孤立的业务数据域。
- AuditProject、AuditArea、AuditAreaRecord 是唯一正式审核数据链。
- 项目资料必须携带 project_id，绝不允许跨项目检索或引用。
- 全局法规与当前项目资料可同时被 Agent 使用，但页面必须清晰标记来源。
- 证据、引用、模型判断、人工确认和最终制品均可追溯。
- 异常优先、提交阻断、NC 确认和报告质量门禁在后端统一执行。

## 审核工作流

    H5 / Web Agent
    会话、流式、语音、照片、确认卡
                    |
                    v
    项目审核领域工具
    项目资料、证据、多条款、异常、NC、报告
                    |
                    v
    AuditProject / AuditArea / AuditAreaRecord
    唯一正式审核数据链
                    |
                    v
    Word 报告、区域记录、NC 汇总、ZIP 资料包

正式记录关系：

    AuditProject -> AuditArea -> AuditPlanItem -> AuditAreaRecord -> InspectionRecordItem

AI 会话、现场证据、草稿、媒体、NC 和制品均带有 project_id。AI 草稿只在审核员确认后写入正式 InspectionRecordItem。

## 已实现能力

### P0：数据链与部署目标

- H5 旧审核任务链接统一跳转到正式 AI 审核会话，不再误用普通检查记录 ID。
- 现场证据会真实调用后端；刷新后仍显示已保存证据和已确认审核记录。
- 条款来自计划项、模板和候选匹配，不再硬编码为 7.1。
- Web Agent 携带项目、会话、计划项和页面上下文；确认操作执行受控后端写入。
- 生产配置与部署脚本统一指向 49.232.213.79。
- 审计日志对长项目路径保留完整路径到 detail，不影响业务事务。

### P1：现场审核 Agent

- 项目审核会话、证据提交、证据条目、AI 草稿和人工确认。
- 一条证据可生成多个候选条款草稿，保存证据质量、理由、置信度和引用。
- 文字、语音和照片均可作为会话证据；上传照片与项目、会话强绑定。
- Agent 同时检索全局法规与当前项目资料，检索结果带 source_scope。
- 未处理草稿、证据不足和必要附件缺失会阻断提交。
- 异常确认记录可生成 NC 草稿，组长或管理员确认后进入整改。

### P2：审核交付闭环

- 项目级完整性和一致性检查，报告和资料包生成前执行质量门禁。
- 版本化报告快照保存记录、证据、照片、理由、置信度和引用。
- 生成区域审核记录 Word、审核报告 Word、NC 汇总和完整 ZIP 资料包。
- ZIP 包含 manifest.json，列出路径、大小和 SHA-256。
- 制品任务持久化进度、失败原因，支持重试。
- H5 提供今日审核、AI 现场审核、异常优先草稿和提交确认流程。

### P3：知识库混合检索与用户决策闭环

- **智能初审与用户决策闭环**：资料上传后系统自动执行两阶段一致性预审；若存在行业或企业特征偏差，暂停高开销向量计算以节省算力，弹出确认框由用户自主决策是否建立索引或仅作文件归档，列表支持随时补建索引。
- **多粒度 N-gram 与标题加权混合检索**：支持 2-gram / 3-gram 及专业代号分词，解决自然语言长问句检索匹配难题；引入 15% 文档名主意图加权（Title Bonus），确保真实答案片段排在首位（Top 1）。
- **Web UI 全局高对比度与紧凑化重构**：修复全局 Ghost 按钮对比度问题，将项目详情头部卡片压缩至 150px 高度紧凑信息条与快捷动作区；审核计划支持多日日程看板与表格视图。
- **LLM 双重容灾热备**：主模型 `deepseek-v4-flash` + 备用模型 `DeepSeek-V3.2`，遇故障自动平滑转移。

### P4：智审 Agent、审核记录分层与首末次会议闭环

- **智审 Agent 品牌与全链路动作注册**：前端与提示词统一命名为「智审 Agent」，支持服务端受控执行：审核组指派、排期计划批量录入、首末次会议纪要生成、现场证据提交与三级评价智能研判。
- **正式审核记录任务归集与历史版本展开**：按审核任务 1 对 1 归集现场审核单，默认展示当前有效版本；支持展开行一键追溯全量历史填报版本（V1、V2...）与结论演进；检查项列表完整呈现客观证据、审核发现与整改建议。
- **首末次会议智能入库**：明确区分计划排期（`AuditPlanItem`）与会议记录（`CommunicationMeeting`），支持自然语言智能生成首末次会议记录卡片并一键落库。
- **H5 现场 AI 审核体验重构**：多条款分析进度整合至按钮下方，进度百分比与任务项数严格基于模板项精确计算。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 后端 | Python 3.11+、FastAPI、SQLAlchemy Async、Alembic、PostgreSQL |
| Web 管理端 | React 18、TypeScript、Vite、Ant Design |
| H5 现场端 | Vue 3、Vite、Vant |
| 文本模型 | deepseek-v4-flash（主） / DeepSeek-V3.2（热备） |
| 现场能力 | 多模态照片分析、浏览器语音识别、会话媒体上传、离线缓存 |
| 知识检索 | 全局法规知识库 + project_id 强约束多粒度混合检索项目知识库 |
| 交付 | python-docx、版本快照、带校验清单的 ZIP |

## 仓库结构

    expert_app_opencode/
    ├── backend/
    │   ├── alembic/                 # PostgreSQL 增量迁移
    │   ├── app/
    │   │   ├── models/              # 审核、会话、证据、项目资料、制品
    │   │   ├── routers/             # REST / SSE API
    │   │   ├── schemas/             # Pydantic 请求与响应模型
    │   │   ├── services/            # Agent、RAG、证据、报告、制品服务
    │   │   └── middleware/          # JWT、审计等中间件
    │   └── tests/
    ├── web-admin/                   # React 审核管理端
    ├── h5-app/                      # Vue 移动现场审核端
    ├── deploy_server.py             # 生产部署脚本
    └── README.md

## 快速开始

### 环境要求

- Python 3.11+
- Node.js ^20.19.0 或 >=22.12.0
- PostgreSQL
- backend/.env 已配置数据库、JWT、模型服务和文件存储参数

不要把凭据写入 README、前端源码或公开提交；私有仓库中的既有受控配置按当前部署策略保留。

### 后端

    cd backend
    .venv\Scripts\activate
    pip install -r requirements.txt
    alembic upgrade head
    uvicorn app.main:app --host 127.0.0.1 --port 8000

### Web 管理端

    cd web-admin
    npm install
    npm run dev

默认地址：http://127.0.0.1:5173

### H5 现场端

    cd h5-app
    npm install
    npm run dev

默认地址：http://127.0.0.1:5174/h5/

## 数据库迁移

本地与生产共享同一 PostgreSQL 时，迁移只需在本地执行一次：

    cd backend
    alembic upgrade head

相关迁移示例：

- `a49ad7e0875f`：正式审核会话、证据、AI 草稿、项目资料与知识片段、制品任务
- `drop_enterprise_instruments`：删除企业「计量器具」表 `enterprise_instruments`

## 项目 Agent API

所有项目 Agent 接口位于 /api/audit-projects/{project_id}，并验证当前用户对项目的访问权限。

| 能力 | 接口 |
| --- | --- |
| 项目资料列表/上传 | GET/POST /documents |
| 项目资料重新索引 | POST /documents/{document_id}/reindex |
| 合并检索 | POST /knowledge/search |
| 审核会话 | GET/POST /sessions |
| 获取会话 | GET /sessions/{session_id} |
| 会话照片 | POST /sessions/{session_id}/media |
| 提交证据并生成草稿 | POST /sessions/{session_id}/evidence |
| 确认或驳回草稿 | POST /sessions/{session_id}/drafts/confirm |
| 会话质量检查 | POST /sessions/{session_id}/quality-check |
| 提交正式区域记录 | POST /sessions/{session_id}/submit |
| 确认 NC 草稿 | POST /nonconformities/{nc_id}/confirm |
| 项目质量门禁 | POST /quality-check |
| 生成制品 | POST /artifacts/generate |
| 查询/重试制品 | GET /artifacts、POST /artifacts/{artifact_id}/retry |
| 下载资料包 | GET /package |

## 知识库与项目资料

### 全局知识库（Web：政策法规）

- 文档以 **文档类型**（法规 / 政策 / 标准 / 细则）分类，不再使用独立「知识分类」字段。
- 支持文件上传（PDF/Word/Excel/TXT）：解析正文后立即建立向量索引。
- 列表不再展示浏览次数；查看详情不再写回 `view_count`。
- 软删除文档时同步删除 `knowledge_embeddings`，检索只命中 `is_deleted=false` 且 `status=effective` 的文档。

### 项目资料与知识库（审核项目详情页）

- 列表接口轻量化：不加载片段正文与 embedding，仅 `COUNT` 片段数；`extracted_text` 列表侧 defer。
- 「在项目资料中查找」提供检索进度（阶段、用时、进度条）；语义检索超时前端 120s。
- 合并检索返回 `source_scope`：`project`（本项目）或 `global_regulation`（全局法规）。

## 项目级 RAG 隔离规则

1. 项目资料和项目知识片段必须携带 project_id。
2. 项目知识片段通过项目与文档的复合关联约束，避免跨项目引用。
3. 检索同时返回全局法规和当前项目资料；source_scope 为 global_regulation 或 project。
4. Web 与 H5 必须显示来源域和文档标题，不能把全局法规误标为项目资料。
5. AI 草稿和报告快照保存使用过的引用，保证可追溯。
6. 全局法规检索必须排除已软删除与非 effective 文档，避免已删知识库被引用。

## 质量门禁与提交规则

- 有待确认草稿时不能提交区域审核记录。
- 证据质量不足、必要附件缺失或高风险异常会作为阻断项或警告项返回。
- 不符合项只有在组长或管理员确认后进入正式整改流程。
- 已提交会话不可再采集证据、确认草稿或重复写入；后端提交接口幂等返回已提交快照。
- 项目报告与资料包生成前必须通过完整性和一致性检查。

## 验证命令

    # 后端
    cd backend
    python -m pytest tests -q

    # Web
    cd ..\web-admin
    npx tsc --noEmit
    npm run build

    # H5
    cd ..\h5-app
    npm run type-check
    npm run build

    # 工作区
    cd ..
    git diff --check

浏览器端到端验证至少覆盖：

1. 从 H5 审核计划项进入正式 AI 会话。
2. 保存一条文字、语音或照片证据，刷新后仍看到证据及确认记录。
3. 生成多个候选条款，人工确认后检查正式区域记录和计划项状态。
4. 从 Web 验证项目资料来源标识、质量门禁、制品任务和 ZIP manifest.json。
5. 在桌面 Web 与小屏、横屏 H5 下检查无溢出、无重叠、按钮可触达。

面向客户的售前演示顺序、客户验收点与签字模板见 [客户演示与验收手册](docs/客户演示与验收手册.md)。

## 生产部署

生产部署目标由下列文件统一维护：

- deploy_server.py
- web-admin/.env.production
- h5-app/.env.production

目标主机为 49.232.213.79:22，用户为 ubuntu。部署前确认服务器凭据、数据库连通性、Alembic 当前版本和前端构建产物；部署后验证 Web、H5、后端健康检查和一个正式审核会话。

## 角色

| 角色 | 权限 |
| --- | --- |
| super_admin | 全部权限 |
| admin | 项目、模板、团队、报告、NC 确认与制品管理 |
| expert | 执行分配的现场审核、提交证据、确认草稿 |
| auditor | 只读查看 |

## 提交规范

    feat: 新能力
    fix: 缺陷修复
    docs: 文档变更
    test: 测试变更
    refactor: 内部重构
    chore: 构建或工具调整

提交前执行对应模块测试，并保留用户已有的未关联工作区改动。不要使用破坏性 Git 命令重置工作树。

## 许可证

MIT License

## Latest Delivery Notes

### 2026-07-21

- **知识库精简**：移除「分类」与「浏览次数」；上传/列表仅依赖文档类型。
- **企业详情**：移除「计量器具」标签，并 drop 表 `enterprise_instruments`。
- **审核项目详情**：标签顺序调整为「审核组 → 审核计划 → …」。
- **项目资料列表性能**：不再 `selectinload` 全部 chunks（原 ~11s → ~0.5s）。
- **项目知识检索 UX**：检索中展示阶段、用时与进度，避免空白等待。
- **全局 RAG 范围**：过滤已删除/非 effective 文档；删除时清理 embedding。
- **Agent 最终答复恢复**：工具成功后模型返回空内容时自动重试，仍失败则基于工具结果整理答案与引用来源。

### 2026-07-22 Fixes

- **任务列表按钮文案**：未完成显示“继续检查”，已完成显示“重新检查”；“详情”统一改为“查看”。
- **现场记录标签页**：点击“查看检查”不再直接进入修改页；已完成任务先进入只读正式审核记录页面；“修改”按钮才进入重新检查/编辑表单。
- **只读记录页**：彻底隐藏保存、提交、AI 评估、上传照片、所有表单编辑字段，并添加事件处理器保护层。
- **资料包/成果默认值**：默认生成 package ZIP（包含报告、区域记录、NC 汇总、清单、manifest.json 和 SHA-256）；避免发送空请求导致遗漏。
- **全局表格固定列**：修复 hover 划过行时背景过渡闪现问题（固定列使用不透明色 + 0s transition，覆盖 .ant-table-cell-row-hover）。
- **生产构建**：成功打包（3142 模块，11.9s）；后端 11 条 artifact/storage 测试全通过。
- **统一性**：所有“查看”入口均优先展示已完成记录的只读详情，避免直接进入编辑。

部署地址（生产共享数据库无需本地迁移）：`http://49.232.213.79:3000/audit-projects/...`（Web），`:5173`（H5），`:8000`（API）。

### 既有能力

- H5 正式审核会话支持流式 Agent、项目上下文、文字/语音/照片证据与确认卡写入。
- 资料包为可重试后台任务，质量门禁通过后下载最新版本。
- 生产验证地址：`49.232.213.79`（Web `:3000`，H5 `:5173`，API `:8000`）。
