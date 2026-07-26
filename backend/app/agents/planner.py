"""轻量目标规划器（plan-and-execute）。

把「准备明天对 X 企业的审核」这类目标，自主拆解为对 tool_registry 中工具的多步调用，
执行后汇总。这是从"反应式工具循环"迈向"目标驱动"的一步。

设计取舍：
- 采用 **plan-then-execute**（先出计划再执行）而非完全自由的 ReAct，规划更可控、可展示、
  Token 更省，也便于前端把"计划步骤"可视化。
- 所有工具都是只读的（见 tool_registry），因此规划器不会产生未经确认的写入；
  若需要写入，由上层把结论转成 agent_actions 的 action_proposal 交用户确认。
- 步数设硬上限，规划用 cheap 档、汇总用 standard 档，控制成本。
"""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm_gateway import LLMTier, llm_gateway
from app.agents.tool_registry import tool_registry
from app.models.user import User

MAX_PLAN_STEPS = 6

_PLAN_SYSTEM = """你是审核工作的规划助手。给定用户目标和可用工具，制定一个最小充分的执行计划。
只能使用提供的工具。输出严格 JSON：
{"steps": [{"tool": "工具名", "args": {...}, "why": "这一步要解决什么"}], "final_goal": "最终要产出什么"}
不要包含解释性文字。步数不超过 %d 步；能少则少；参数必须来自用户目标或上下文。""" % MAX_PLAN_STEPS


def _tools_brief() -> str:
    lines = []
    for t in tool_registry.list():
        params = ", ".join((t.parameters.get("properties") or {}).keys())
        lines.append(f"- {t.name}({params}): {t.description}")
    return "\n".join(lines)


async def run_plan(
    *,
    goal: str,
    context: dict,
    db: AsyncSession,
    user: User,
) -> AsyncGenerator[dict, None]:
    """执行一次规划，流式产出事件：plan / step_start / step_result / content / done。"""
    ctx_text = json.dumps(context or {}, ensure_ascii=False)

    # 1) 规划（cheap 档）
    try:
        plan = await llm_gateway.complete_json(
            messages=[
                {"role": "system", "content": _PLAN_SYSTEM},
                {"role": "user", "content": f"可用工具：\n{_tools_brief()}\n\n上下文：{ctx_text}\n\n目标：{goal}"},
            ],
            tier=LLMTier.CHEAP,
            call_type="planner_plan",
            db=db,
            user_id=str(user.id),
        )
    except Exception as exc:
        yield {"type": "error", "content": f"规划失败：{exc}"}
        return

    steps = plan.get("steps") if isinstance(plan, dict) else None
    if not isinstance(steps, list) or not steps:
        yield {"type": "error", "content": "未能生成可执行计划"}
        return
    steps = steps[:MAX_PLAN_STEPS]

    yield {
        "type": "plan",
        "steps": [{"tool": s.get("tool"), "why": s.get("why")} for s in steps if isinstance(s, dict)],
        "final_goal": plan.get("final_goal"),
    }

    # 2) 执行（工具只读）
    observations: list[dict] = []
    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        tool_name = step.get("tool")
        args = step.get("args") or {}
        # 允许规划器省略已知上下文参数，自动补齐
        for key in ("project_id", "enterprise_id", "record_id"):
            if key in (tool_registry.get(tool_name).parameters.get("properties", {}) if tool_registry.get(tool_name) else {}):
                args.setdefault(key, context.get(key))
        yield {"type": "step_start", "index": idx, "tool": tool_name, "why": step.get("why")}
        result = await tool_registry.execute(tool_name, db, user, args)
        observations.append({"tool": tool_name, "result": result})
        yield {"type": "step_result", "index": idx, "tool": tool_name, "ok": not (isinstance(result, dict) and result.get("error"))}

    # 3) 汇总（standard 档，流式）
    synthesis_prompt = (
        f"用户目标：{goal}\n\n"
        f"各步工具执行结果（JSON）：\n{json.dumps(observations, ensure_ascii=False)[:12000]}\n\n"
        "请基于以上结果，用中文给出面向审核员的、可操作的结论。"
        "必须忠于工具结果，不得编造；如信息不足请明确指出缺什么。"
        "涉及法规引用时标注来源。"
    )
    try:
        async for delta in llm_gateway.stream(
            messages=[
                {"role": "system", "content": "你是资深认证审核专家，负责把检索到的信息整理成审核准备结论。"},
                {"role": "user", "content": synthesis_prompt},
            ],
            tier=LLMTier.STANDARD,
            call_type="planner_synthesis",
            db=db,
            user_id=str(user.id),
        ):
            yield {"type": "content", "content": delta}
    except Exception as exc:
        yield {"type": "error", "content": f"汇总失败：{exc}"}
        return

    yield {"type": "done"}
