# AI / Agent 层

分两代：早期的「LLM 建议」能力（`llm_service` + `rag_service`），
和 2026-07 后建的共享 Agent 运行时（`app/agents/`）。新功能优先接后者。

## 共享运行时 `backend/app/agents/`

| 文件 | 职责 |
|------|------|
| `llm_gateway.py` | 模型分层调用 + 统一落 `LLMCallLog`；`complete` / `complete_json` / `stream` |
| `tool_registry.py` | 只读工具注册表，对话 Agent 与规划器共用 |
| `planner.py` | plan-then-execute 规划器，`run_plan()` |

**模型分层** `LLMTier`：
- `CHEAP` —— 意图分类、规划步骤、列举（`settings.cheap_model`）
- `STANDARD` —— 对话、报告、证据判定（`settings.standard_model`）
- `VISION` —— 多模态照片（`settings.VISION_LLM_MODEL`，独立 client）

新增 LLM 调用点一律走 gateway，不要直接 new `AsyncOpenAI`——否则丢日志、丢分层。

## 对话 Agent `services/agent_service.py`

- **有界多轮工具循环**：`MAX_TOOL_ROUNDS = 5`，超出即强制收口。
- **22 个工具**：11 个通用（检查项、知识检索、企业历史、模板推荐、照片分析、写回建议），
  11 个正式审核项目上下文追加（项目上下文、审核组、计划项、沟通会议、证据与草稿确认）。
- **SSE 流式**输出；会话持久化到 `AgentConversation` / `AgentMessage`。
- **人在回路强制**：所有写回都不直接落库，而是产出 `action_proposal` 确认卡，
  由用户点确认后调 `POST /api/agent/actions/confirm` 才写。
  动作定义在 `services/agent_actions.py`。加新写操作必须沿用这个模式。

## 证据管线 `services/evidence_agent_service.py` + `routers/project_agent.py`

持久化流程：`AiAuditSession → EvidenceSubmission → EvidenceItem → AiDraftRecord`
→ 用户确认 → `AuditAreaRecord` / `Nonconformity`。

- RAG 接地（项目文档切片 `ProjectKnowledgeChunk` + 知识库 `KnowledgeEmbedding`）。
- 提交证据时先跑照片多模态分析，结论再喂进多条款判定。
- 有质量门禁（`/quality-check`）与成果打包（`/artifacts`、`/package`）。
- ⚠️ 仍是**单次 LLM 调用**，不是自主规划。

## 早期 LLM 能力 `services/llm_service.py`

三类 prompt：
- `SUGGESTION_PROMPT` —— 依据检查项与结果生成检查结论
- `BASIS_PROMPT` —— 给出法规/标准依据
- `FINAL_JUDGMENT_PROMPT` —— 生成整体检查结论

特性：支持流式；结果缓存在 `TaskItemRecord.llm_suggestion` / `llm_basis`；
全部调用落 `LLMCallLog`。

`services/audit_agent.py` 提供审核项目侧的四个能力：
`prepare_audit_with_ai` / `evaluate_evidence_with_ai` / `generate_report_with_ai` /
`suggest_nc_with_ai`。

## 闭环能力

- **反馈闭环**：`AiDraftRecord.was_edited` + `agent_feedback_service`
  （按体系/条款/prompt 版本统计采纳率），暴露在 `GET /api/agent/feedback/stats`；
  负面样本回流为证据分析的 few-shot。
- **长期记忆**：`AgentMemory`（带 `enterprise_id` / `project_id` / `scope`），
  确认的不符合项沉淀为企业级记忆并注入审核准备简报。
- **主动巡检**：`agent_proactive_service` 巡检企业到期 / NC 超期 / 草稿滞留，
  写 `AgentNotification`；由 lifespan 后台轮询驱动。
  ⚠️ 是**进程内轮询**，没上分布式队列（redis/arq）——通知落库不丢，但循环随进程走。

## Agent 端点

```
POST   /api/agent/chat                    # 对话（SSE）
POST   /api/agent/actions/confirm          # 确认写回动作
GET    /api/agent/actions/registry         # 可用动作清单
POST   /api/agent/plan                     # 规划器（SSE）
GET    /api/agent/models                   # 模型分层信息
GET    /api/agent/briefing/{enterprise_id} # 审核准备简报（另有 /stream）
GET    /api/agent/conversations[/{id}]     # 历史会话
GET    /api/agent/feedback/stats           # 采纳率统计
GET    /api/agent/notifications            # 主动通知（PUT /{id} 标记已读）
```

项目级（`/api/audit-projects/{project_id}/...`，见 `routers/project_agent.py`）：
`documents` · `knowledge/search` · `sessions[/{id}]` · `sessions/{id}/media` ·
`sessions/{id}/evidence` · `sessions/{id}/drafts/confirm` · `sessions/{id}/quality-check` ·
`sessions/{id}/submit` · `nonconformities/{id}/confirm` · `artifacts[/generate]` · `package`

## 已知缺口

- 引用自校验 / 反思环节按需求暂缓，未实现。
- 无分布式任务队列，主动巡检是进程内轮询。
- 前端尚未接入新端点（反馈看板、通知铃铛、规划器入口）——后端已就绪。
- （历史）mobile-app 的 Agent 写回被故意禁用（`advisoryOnly`）；mobile-app 已于 2026-11-23 停用。原因见
  [data-model.md](data-model.md) 的三套记录模型。

## 前端调用示例（流式）

```javascript
const response = await fetch(`${API_URL}/api/llm/suggestion/stream`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
  body: JSON.stringify({ task_id, record_id, use_cache: true }),
})
const reader = response.body.getReader()
// 逐块读取...
```

## 相关环境变量

见 [ops.md](ops.md) 的「LLM / RAG / 多模态」一节。
