# 面向一线审核员的 Agent 改造规划

> 本规划面向开发团队，用于指导下一阶段开发。与已有的 `agent_transformation_proposal.md`（从零构建的总体设想）不同，本规划**基于当前代码实际状态**，聚焦一个目标：**让一线审核员用起来不再"麻烦"，把已有的"聊天机器人"进化为真正能干活的"检查搭档"。**

## 一、现状诊断（基于当前代码）

系统**已经有一个 Agent**，不是从零开始。现有实现：

| 已实现 | 位置 | 说明 |
|--------|------|------|
| Function-Calling Agent | `backend/app/services/agent_service.py`（768 行） | 9 个工具、SSE 流式输出 |
| 9 个工具 | 同上 | 列检查项/查详情/查汇总/生成判定/搜知识库/查企业历史/推荐模板/分析照片/建议填写 |
| RAG 检索 | `backend/app/services/rag_service.py` | 已接入 `search_knowledge_base` 工具 |
| 多模态照片分析 | `backend/app/services/multimodal_service.py` | 已接入 `analyze_photo` 工具 |
| H5 对话面板 | `h5-app/src/components/agent/AgentChatPanel.vue` | 底部弹窗，55% 高度，带快捷指令 |
| Web 侧边栏 | `web-admin/src/components/agent/AgentSidebar.tsx` | 右侧助手面板 |
| 对话接口 | `backend/app/routers/agent.py` | `POST /api/agent/chat`（SSE） |

## 二、为什么对一线审核员还是"麻烦"（核心痛点）

诊断出 6 个具体问题，每一个都对应明确的代码位置：

1. **只会"提建议"，不会"动手"** —— `fill_check_result` 等工具只返回建议文本，不写回检查记录。审核员看完建议还得自己手动填一遍，等于多了一步。
2. **单轮工具调用，不能连续推理** —— `agent_service.py:335` 的续写调用**没有再传 `tools`**，Agent 调完一轮工具就必须回答，无法"查历史→查法规→给判定"这样的多步链路。
3. **被动、藏得深** —— 必须点按钮才打开，且只有进入某条检查记录后才有用；无法用对话"从零发起一次检查"。
4. **移动端（mobile-app）完全没有 Agent** —— 而 CLAUDE.md 明确 mobile-app 是专家/审核员的主力客户端。
5. **输入门槛高** —— 现场审核员戴手套、手忙，只能打字。无语音输入、无"拍照即分析"的一键入口。
6. **无会话记忆** —— 每次对话历史由前端传入，服务端不落库，换设备/刷新即丢失，谈不上"长期搭档"。

## 三、改造目标与原则

**目标：从"检查员操作的工具"变成"检查员的 AI 搭档"——审核员说目标，Agent 干活并回填，人只做确认。**

设计原则：
- **人在回路（Human-in-the-Loop）**：检查结论有法律效力，Agent 可写回但必须经审核员一键确认，绝不自动提交。
- **改造优先于新建**：复用已有 9 个工具和 RAG/多模态能力，不推倒重来。
- **降门槛第一**：现场场景下，减少一次点击、一次打字比增加一个功能更有价值。
- **成本可控**：多步循环设上限，避免 Token 失控。

## 四、分阶段开发任务（按优先级排序）

改造分 4 个阶段，**每个阶段独立可上线、可验证**。建议严格按顺序做——前一阶段是后一阶段的基础。

---

### 阶段一：让 Agent"能动手"（最高优先级，约 1–1.5 周）

**价值**：这是投入产出比最高的一步。审核员最烦的就是"AI 说了一堆，我还得自己填"。让 Agent 的建议变成"一键采纳即回填"，体验立刻不同。

**后端任务**

1. 修复多轮工具调用（`agent_service.py:335` 附近）
   - 续写调用改为循环：`while` 循环中持续传 `tools=TOOLS, tool_choice="auto"`，直到模型返回纯文本或达到最大轮次。
   - 设 `MAX_TOOL_ROUNDS = 5`（可配），防止死循环和 Token 失控。
   - 验证标准：问"这家企业上次哪些不合格，对照法规现在这项该怎么判"，Agent 能连续调用 `get_enterprise_history` → `search_knowledge_base` → 给出判定，一次完成。

2. 新增"写操作"工具（需带确认机制）
   - `apply_check_result(item_id, result, problem_description)`：写回 `InspectionRecordItem` 的判定与问题描述。
   - `apply_final_verdict(record_id, verdict, comment)`：写回最终判定。
   - 关键：这些工具**不直接落库**，而是返回 `{type: "action_proposal", action: "...", payload: {...}}` 事件，由前端弹确认卡片，审核员点"采纳"后再调用真正的写接口（复用现有 `/api/records` 或 `/api/tasks` 写接口）。
   - SSE 事件类型扩展：在现有 `content/tool_call/tool_result/done/error` 基础上新增 `action_proposal`。

**前端任务（H5 优先）**

3. `AgentChatPanel.vue` 支持动作确认卡片
   - 新增 `AgentActionCard.vue`：展示"Agent 建议把第 3 项判为『不合格』，问题描述：……"，带【采纳并填写】【修改】【忽略】三个按钮。
   - 点【采纳】→ 调用写接口 → 回填到检查表单 → 面板显示"已填写"。

**交付物**：审核员在对话里说"把这项判为不合格，问题是缺少校验记录"，Agent 生成规范问题描述 + 判定，一键回填到表单。

---

### 阶段二：降低现场输入门槛（约 1 周）

**价值**：现场审核员手不空、环境嘈杂。语音和拍照入口直接决定"愿不愿意用"。

**前端任务（H5 优先，mobile-app 同步）**

4. 语音输入
   - 对话输入框加麦克风按钮，接入浏览器 `Web Speech API`（H5）或系统语音输入；识别文本填入输入框，可编辑后发送。
   - 现场降噪：识别后先展示文本让用户确认，不直接发送。

5. "拍照即分析"一键入口
   - 检查执行页（`InspectionExecution.vue`）拍照后，直接出现【让 AI 看看】按钮 → 调用已有 `analyze_photo` 工具 → 结果直接进对话面板并附动作建议（可衔接阶段一的回填）。

6. 更聪明的快捷指令
   - 现有快捷指令是静态的。改为**根据当前检查项类型动态生成**：如遇 `photo` 类型项显示"分析这张照片"，遇有历史不合格的企业显示"看看上次的问题"。

**交付物**：审核员对着手机说话或拍张照，就能完成一次检查项的记录，几乎不用打字。

---

### 阶段三：Agent 进入移动端 + 会话记忆（约 1–1.5 周）

**价值**：补齐主力客户端；让 Agent 成为"记得住"的搭档。

**后端任务**

7. 会话持久化
   - 新增 `AgentConversation` / `AgentMessage` 模型（参考 `agent_transformation_proposal.md` 第 5.3 节的表设计），写 Alembic 迁移。
   - `/api/agent/chat` 支持 `conversation_id`：不传则新建，传则续接并从库读历史（替代目前完全依赖前端传 `conversation` 数组）。
   - 新增 `GET /api/agent/conversations` 拉取历史会话。

**前端任务（mobile-app，React + antd-mobile）**

8. mobile-app 接入 Agent
   - 参照 H5 的 `api/agent.js` 与 `AgentChatPanel.vue`，在 `mobile-app/src/` 下实现对应的 `services` 调用与对话组件。
   - 复用阶段一、二的动作卡片与语音/拍照能力。
   - 在 `Inspection`、`QuickCheck` 页面加入 Agent 入口。

**交付物**：mobile-app 拥有与 H5 对等的 Agent；对话历史跨设备、跨会话保留。

---

### 阶段四：主动式搭档（约 1.5–2 周）

**价值**：从"你问我答"进化到"我提前帮你想好"。这是与普通聊天机器人拉开差距的关键。

**后端任务**

9. 检查前"准备简报"
   - 新增 `prepare_briefing(enterprise_id)` 能力：编排 `get_enterprise_history` + `search_knowledge_base` + 风险数据，一次生成"企业概况 + 上次遗留问题 + 最新法规变化 + 重点关注清单"。
   - 复用已有 `audit_agent.py` 的 `prepare_audit_with_ai`（避免重复造轮子）。

10. 主动提醒（可选，视资源）
    - 检查即将开始/企业有未整改项时，由 Agent 主动推送提示卡片。

**前端任务**

11. 任务列表/首页展示"AI 检查简报"入口
    - 在 H5 `Home.vue`、mobile-app 任务列表，为每个待办任务加【AI 准备简报】按钮。

**交付物**：审核员出发前点一下，就拿到一份该企业的检查准备简报。

## 五、总体路线图

| 阶段 | 主题 | 预估工时 | 人员 | 上线后审核员感受 |
|------|------|---------|------|----------------|
| 一 | Agent 能动手（多轮工具 + 回填） | 1–1.5 周 | 1 后端 + 1 前端 | "它能帮我填了，不用重复劳动" |
| 二 | 降低现场输入门槛（语音 + 拍照） | 1 周 | 0.5 后端 + 1 前端 | "戴着手套也能用" |
| 三 | 移动端接入 + 会话记忆 | 1–1.5 周 | 1 后端 + 1 前端 | "换手机也记得我" |
| 四 | 主动式搭档（准备简报） | 1.5–2 周 | 1 后端 + 0.5 前端 | "出发前它已经帮我想好了" |
| **合计** | | **约 5–6 周** | | |

> 与 `agent_transformation_proposal.md` 的关系：那份是完整愿景（含 Master/多 Agent 编排等长期目标）。本规划是**近期落地路径**，先把"能动手 + 好用"做扎实。多 Agent 编排（proposal 的 Phase 4）建议放到本规划四个阶段完成、验证有效后再启动。

## 六、给开发人员的关键提醒

1. **人在回路是红线**：任何写回检查结论的操作，都必须经审核员确认。检查结果有法律效力，Agent 只能"建议 + 代填"，不能"自动定论"。（参见 proposal 第 8.2 节）
2. **复用优先**：写回走现有 `/api/records`、`/api/tasks` 接口；简报复用 `audit_agent.py`；不要新建平行逻辑。
3. **多轮循环必须设上限**：`MAX_TOOL_ROUNDS`，并记录每轮 Token，接入现有 `LLMCallLog`。
4. **移动端与 H5 对齐但不照搬**：H5 是 Vue/Vant，mobile-app 是 React/antd-mobile，组件要各自实现，但 API 契约（SSE 事件类型、动作卡片协议）保持一致。
5. **先在 H5 验证再推 mobile-app**：H5 已有完整链路，作为试验田；成熟后再移植，降低返工。

## 七、建议的第一步（本周即可启动）

从**阶段一的多轮工具调用修复**开始——这是当前 Agent 最大的能力短板，改动集中在 `agent_service.py` 一个文件，1–2 天可见效果，且不影响现有 UI。完成后立即接"动作确认卡片"，两周内审核员就能感受到"Agent 会干活了"的明显变化。

