# 数据模型

42 张表，按域分组。ORM 在 `backend/app/models/`，迁移在 `backend/alembic/versions/`（24 个版本）。

## 表清单

**账号与组织**
`users` · `organizations`

**企业档案**
`enterprises` · `enterprise_qualifications` · `enterprise_products` ·
`rectification_records` · `industries`

**模板**
`inspection_templates` · `template_items`（层级结构）

**任务流（旧）**
`inspection_tasks` · `task_item_records`

**记录流**
`inspection_records` · `inspection_record_items`

**审核项目正式流**（核心业务）
`audit_projects` · `audit_team_members` · `audit_plan_items` · `audit_areas` ·
`audit_area_records` · `nonconformities` · `audit_reports` · `communication_meetings`

**证据管线**
`ai_audit_sessions` · `evidence_submissions` · `evidence_items` · `ai_draft_records`

**知识与 RAG**
`knowledge_documents` · `inspection_guidelines` · `knowledge_embeddings` ·
`check_item_regulations` · `template_recommendations` · `photo_analyses`

**项目文档与成果**
`project_documents` · `project_knowledge_chunks` · `project_artifacts`

**Agent 运行时**
`agent_conversations` · `agent_messages` · `agent_memories` · `agent_notifications`

**其他**
`media_files` · `audit_logs` · `llm_call_logs`

### 哪些是软删除

只有挂了 `SoftDeleteMixin` 的模型才有 `is_deleted` / `deleted_at`：
`User` · `Organization` · `Enterprise` · `EnterpriseQualification` · `Industry` ·
`InspectionTemplate` · `TemplateItem` · `InspectionTask` · `InspectionRecord` ·
`KnowledgeDocument` · `MediaFile` · `AuditProject` · `AuditTeamMember` ·
`AuditPlanItem` · `ProjectDocument` · `ProjectArtifact`。

其余表（区域记录、不符合项、报告、证据管线、Agent 表、日志）是**硬删除**——
写查询时不要盲加 `is_deleted == False` 过滤，会直接报字段不存在。

## 关键关系

```
# 模板
InspectionTemplate → TemplateItem (1:N，item 自身可嵌套)

# 任务流
InspectionTask → TaskItemRecord (1:N)
TaskItemRecord → TemplateItem（指向检查项）
MediaFile → InspectionTask 或 TaskItemRecord（可选关联）

# 企业
Enterprise → EnterpriseQualification / Product / Equipment / Personnel / RectificationRecord

# 审核项目正式流
AuditProject → AuditTeamMember, AuditPlanItem, AuditArea, AuditAreaRecord,
               Nonconformity, AuditReport, CommunicationMeeting
AuditPlanItem → InspectionTask（创建计划项时自动建任务）
AuditAreaRecord → InspectionRecordItem（检查项结果）

# 证据管线
AiAuditSession → EvidenceSubmission → EvidenceItem → AiDraftRecord
AiDraftRecord --确认--> InspectionRecordItem / Nonconformity
```

## ⚠️ 核心架构债：三套并行的「检查结果」模型

这是当前最大的技术债，也是"减 SaaS、增 Agent"的首要障碍。

| # | 链路 | 谁在用 |
|---|------|--------|
| 1 | `InspectionTask → TaskItemRecord` | 原 mobile-app 的 QuickCheck / Inspection 页（mobile-app 已于 2026-11-23 停用；表与接口仍在，H5 任务流也会写入） |
| 2 | `InspectionRecord → InspectionRecordItem` | h5-app 与 web-admin 的 Agent 写回（`/api/records/*`） |
| 3 | `AuditProject → AuditAreaRecord → InspectionRecordItem` + 证据管线 | 正式审核流（最完整、最面向未来） |

`services/formal_audit_sync_service.py` 是把 #1 桥接进 #3 的胶水（纯规则，无 AI）。

**直接后果**：mobile-app 的 Agent 动作确认卡（写回）被**故意禁用**（`advisoryOnly`）——
它的页面读任务流表，而 Agent 写回 API 打的是记录流表，两套表对不上。
Agent 工具也必须按目标模型分别特判。

**因此**：新增检查结果相关功能时，优先落在 #3；不要再给 #1/#2 加新字段或新分支。

## 两条业务流程

1. **简易检查**：`InspectionTask → TaskItemRecord → InspectionRecordItem`
2. **认证审核**：`AuditProject → AuditPlanItem → InspectionTask`（自动创建）

审核项目关键实体：
- `AuditProject` —— 认证审核顶层容器（初次 / 监督 / 再认证）
- `AuditPlanItem` —— 工作任务单元，创建时自动生成 `InspectionTask`
- `AuditAreaRecord` —— 支持多人协同记录的现场记录
- `Nonconformity` —— 不符合项，严重程度 major / minor / observation
- `AuditReport` —— 报告，导出 `/api/audit-projects/{id}/export/word|pdf`

## 模板项检查类型

`TemplateItem.check_type` 取值：
`radio`（合格/不合格/不适用）· `checkbox`(多选) · `text` · `number`（带 min/max）·
`score`（带合格阈值）· `photo`（必须拍照）

## 角色

| 角色 | 权限 |
|------|------|
| `super_admin` | 全系统 |
| `admin` | 模板 / 任务 / 企业管理 |
| `expert` | 执行检查、提交记录（移动端主要用户），数据范围限于分配给自己的 |
| `auditor` | 只读复核，可看全部业务数据 |

判断一律走 `app/utils/roles.py`，不要硬编码字符串比较。

## 迁移流程（重要：本地远程共用一个库）

本地开发与部署服务器连的是**同一个远程 PostgreSQL**
（`PG_HOST=49.232.213.79`，`PG_DB=db_expert_claude`），所以：

- **迁移只在本地跑一次**，部署脚本不再执行迁移。
  ```bash
  cd backend && alembic revision --autogenerate -m "描述" && alembic upgrade head
  ```
- **本地测试会写到线上数据**。冒烟脚本、手工测试都直接落生产库，
  测完用 `scripts/clear_db_records.py` 清理。
- 连接默认值同时硬编码在 `app/config.py`，`backend/.env` 里是真实凭据。
