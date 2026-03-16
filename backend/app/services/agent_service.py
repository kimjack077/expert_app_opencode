import json
from typing import AsyncGenerator, Optional
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.record import InspectionRecord, InspectionRecordItem
from app.models.template import TemplateItem
from app.models.enterprise import Enterprise


AGENT_SYSTEM_PROMPT = """你是EFIS系统的现场检查AI助手。你正在辅助检查员完成现场检查。

当前检查上下文（已提供）：
- 企业：{enterprise_name}
- 检查模板：{template_name}
- 检查记录ID：{record_id}
- 当前检查项：{current_item_title}
- 检查方法：{check_method}
- 法规依据：{legal_basis}

你可以调用以下工具：
1. get_check_item_details - 获取检查项的详细信息
2. get_inspection_summary - 获取当前检查的汇总情况
3. generate_final_verdict - 基于所有检查项结果，生成最终判定建议

重要：当用户询问检查汇总或生成最终判定时，你应该**主动调用** get_inspection_summary 或 generate_final_verdict 工具来获取数据，不要询问用户！

回答要求：
- 简洁专业，适合手机端阅读
- 法规引用要具体到条款号
- 判定建议需给出理由
- 使用Markdown格式，但不要过度使用
- 重要内容用**加粗**标记
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_check_item_details",
            "description": "获取指定检查项的详细信息，包括检查方法、法规依据、标准参考",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "检查项ID"
                    }
                },
                "required": ["item_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_inspection_summary",
            "description": "获取当前检查记录的汇总情况：已检查项数、合格/不合格数、未检查数",
            "parameters": {
                "type": "object",
                "properties": {
                    "record_id": {
                        "type": "string",
                        "description": "检查记录ID"
                    }
                },
                "required": ["record_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_final_verdict",
            "description": "基于所有检查项结果，生成最终判定建议",
            "parameters": {
                "type": "object",
                "properties": {
                    "record_id": {
                        "type": "string",
                        "description": "检查记录ID"
                    }
                },
                "required": ["record_id"]
            }
        }
    }
]


class AgentService:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            timeout=settings.LLM_TIMEOUT,
        )
        self.model = settings.LLM_MODEL

    async def chat_stream(
        self,
        message: str,
        context: dict,
        conversation: list,
        db: AsyncSession,
    ) -> AsyncGenerator[dict, None]:
        context_info = await self._build_context(context, db)
        
        system_prompt = AGENT_SYSTEM_PROMPT.format(
            enterprise_name=context_info.get("enterprise_name", "未知企业"),
            template_name=context_info.get("template_name", "未知模板"),
            record_id=context_info.get("record_id", ""),
            current_item_title=context_info.get("current_item_title", "无"),
            check_method=context_info.get("check_method", "未指定"),
            legal_basis=context_info.get("legal_basis", "未指定"),
        )

        messages = [{"role": "system", "content": system_prompt}]
        
        for msg in conversation[-10:]:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })
        
        messages.append({"role": "user", "content": message})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
                stream=True,
            )

            tool_calls_buffer = {}
            current_tool_call = None
            
            async for chunk in response:
                if not chunk.choices:
                    continue
                    
                delta = chunk.choices[0].delta
                
                if delta.content:
                    yield {"type": "content", "content": delta.content}
                
                if delta.tool_calls:
                    for tool_call_delta in delta.tool_calls:
                        idx = tool_call_delta.index
                        
                        if idx not in tool_calls_buffer:
                            tool_calls_buffer[idx] = {
                                "id": "",
                                "function": {"name": "", "arguments": ""}
                            }
                        
                        if tool_call_delta.id:
                            tool_calls_buffer[idx]["id"] = tool_call_delta.id
                        if tool_call_delta.function:
                            if tool_call_delta.function.name:
                                tool_calls_buffer[idx]["function"]["name"] = tool_call_delta.function.name
                            if tool_call_delta.function.arguments:
                                tool_calls_buffer[idx]["function"]["arguments"] += tool_call_delta.function.arguments

                if chunk.choices[0].finish_reason == "tool_calls":
                    for idx in sorted(tool_calls_buffer.keys()):
                        tool_call = tool_calls_buffer[idx]
                        tool_name = tool_call["function"]["name"]
                        tool_args = json.loads(tool_call["function"]["arguments"] or "{}")
                        
                        yield {"type": "tool_call", "tool": tool_name, "status": "calling"}
                        
                        tool_result = await self._execute_tool(
                            tool_name, tool_args, context, db
                        )
                        
                        yield {"type": "tool_result", "tool": tool_name, "status": "done"}
                        
                        messages.append({
                            "role": "assistant",
                            "tool_calls": [{
                                "id": tool_call["id"],
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": tool_call["function"]["arguments"]
                                }
                            }]
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": json.dumps(tool_result, ensure_ascii=False)
                        })
                    
                    tool_calls_buffer = {}
                    
                    continue_response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        max_tokens=settings.LLM_MAX_TOKENS,
                        temperature=settings.LLM_TEMPERATURE,
                        stream=True,
                    )
                    
                    async for chunk in continue_response:
                        if chunk.choices and chunk.choices[0].delta.content:
                            yield {"type": "content", "content": chunk.choices[0].delta.content}

            yield {"type": "done", "content": ""}

        except Exception as e:
            print(f"[Agent] Stream error: {e}")
            yield {"type": "error", "content": str(e)}

    async def _build_context(self, context: dict, db: AsyncSession) -> dict:
        result = {
            "enterprise_name": "未知企业",
            "template_name": "未知模板",
            "current_item_title": "无",
            "check_method": "未指定",
            "legal_basis": "未指定",
            "record_id": context.get("record_id", ""),
        }

        record_id = context.get("record_id")
        if record_id:
            stmt = select(InspectionRecord).where(InspectionRecord.id == record_id)
            db_result = await db.execute(stmt)
            record = db_result.scalar_one_or_none()
            if record:
                result["template_name"] = getattr(record, 'template_name', '未知模板') or "未知模板"
                result["enterprise_name"] = record.enterprise_name or "未知企业"

        current_item_id = context.get("current_item_id")
        if current_item_id:
            item = await db.get(InspectionRecordItem, current_item_id)
            if item:
                result["current_item_title"] = item.item_title or "未知检查项"
                result["check_method"] = item.item_check_method or "未指定"
                result["legal_basis"] = item.item_legal_basis or "未指定"

        return result

    async def _execute_tool(
        self,
        tool_name: str,
        args: dict,
        context: dict,
        db: AsyncSession,
    ) -> dict:
        if tool_name == "get_check_item_details":
            return await self._tool_get_check_item_details(args.get("item_id"), context, db)
        elif tool_name == "get_inspection_summary":
            return await self._tool_get_inspection_summary(args.get("record_id"), db)
        elif tool_name == "generate_final_verdict":
            return await self._tool_generate_final_verdict(args.get("record_id"), db)
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    async def _tool_get_check_item_details(
        self,
        item_id: Optional[str],
        context: dict,
        db: AsyncSession,
    ) -> dict:
        if not item_id:
            item_id = context.get("current_item_id")
        
        if not item_id:
            return {"error": "未指定检查项ID"}

        item = await db.get(InspectionRecordItem, item_id)
        if not item:
            return {"error": "检查项不存在"}

        return {
            "title": item.item_title,
            "description": item.item_description,
            "check_method": item.item_check_method,
            "legal_basis": item.item_legal_basis,
            "standard_ref": item.item_standard_ref,
            "check_type": item.item_check_type,
            "risk_level": item.item_risk_level,
            "current_result": item.radio_value or item.score_value or item.numeric_value or item.text_value,
            "problem_description": item.problem_description,
        }

    async def _tool_get_inspection_summary(
        self,
        record_id: Optional[str],
        db: AsyncSession,
    ) -> dict:
        if not record_id:
            return {"error": "未指定检查记录ID"}

        result = await db.execute(
            select(InspectionRecordItem).where(
                InspectionRecordItem.record_id == record_id
            )
        )
        items = result.scalars().all()

        if not items:
            return {"error": "检查记录无检查项"}

        total = len(items)
        passed = 0
        failed = 0
        not_applicable = 0
        unchecked = 0
        failed_items = []

        for item in items:
            radio = item.radio_value
            if radio == "pass":
                passed += 1
            elif radio == "fail":
                failed += 1
                failed_items.append({
                    "title": item.item_title,
                    "problem": item.problem_description
                })
            elif radio == "na":
                not_applicable += 1
            else:
                unchecked += 1

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "not_applicable": not_applicable,
            "unchecked": unchecked,
            "failed_items": failed_items,
        }

    async def _tool_generate_final_verdict(
        self,
        record_id: Optional[str],
        db: AsyncSession,
    ) -> dict:
        summary = await self._tool_get_inspection_summary(record_id, db)
        
        if "error" in summary:
            return summary

        if summary["unchecked"] > 0:
            summary["warning"] = f"还有 {summary['unchecked']} 项未检查，建议全部完成后再出具最终判定"

        if summary["failed"] == 0:
            summary["suggested_verdict"] = "pass"
            summary["suggested_verdict_text"] = "合格"
        elif summary["failed"] <= 2 and summary["passed"] > summary["failed"] * 3:
            summary["suggested_verdict"] = "partial_pass"
            summary["suggested_verdict_text"] = "基本合格"
        else:
            summary["suggested_verdict"] = "fail"
            summary["suggested_verdict_text"] = "不合格"

        return summary


agent_service = AgentService()
