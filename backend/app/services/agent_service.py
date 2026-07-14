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
from app.models.task import TaskItemRecord
from app.models.media import MediaFile
from app.services.rag_service import rag_service
from app.services.template_recommendation_service import template_recommendation_service
from app.services.multimodal_service import multimodal_service


AGENT_SYSTEM_PROMPT = """你是EFIS系统的现场检查AI助手。你正在辅助检查员完成现场检查。

当前检查上下文（已提供）：
- 企业：{enterprise_name}
- 检查模板：{template_name}
- 检查记录ID：{record_id}
- 当前检查项：{current_item_title}
- 检查方法：{check_method}
- 法规依据：{legal_basis}
- 待分析照片：{media_hint}

你可以调用以下工具：
1. list_check_items - 列出所有检查项及其ID、标题和判定结果。当用户询问"第一个检查项"或"某项检查"时，**必须先调用此工具**获取检查项ID
2. get_check_item_details - 获取指定检查项的详细信息
3. get_inspection_summary - 获取当前检查的汇总情况
4. generate_final_verdict - 基于所有检查项结果，生成最终判定建议（仅预览，不写入）
5. search_knowledge_base - 搜索知识库法规，获取相关法规依据
6. get_enterprise_history - 获取企业历史检查记录
7. recommend_template - 为企业推荐合适的检查模板
8. analyze_photo - 分析检查照片，识别合规问题
9. fill_check_result - 分析用户描述的检查发现，给出判定建议（仅建议文本，不生成操作卡片）
10. apply_check_result - 当用户已明确给出判定意见并希望记录时，生成"检查结果确认卡片"，审核员点击确认后才会真正写入
11. apply_final_verdict - 当用户要求生成并记录最终判定时，生成"最终判定确认卡片"，审核员点击确认后才会真正写入

重要规则：
- 当用户询问某个检查项（如"第一个检查项"、"第二项"等）时，**必须先调用 list_check_items 获取检查项列表和ID**，然后再调用 get_check_item_details 获取详情
- 当用户询问检查汇总时，你应该**主动调用** get_inspection_summary 工具来获取数据，不要询问用户！
- 当用户明确表达了判定意见（如"这项不合格，问题是缺少校验记录"）时，**必须调用 apply_check_result** 生成确认卡片，而不是只用文字描述——审核员需要能一键采纳
- 当用户要求"生成最终判定"且希望记录结论时，**调用 apply_final_verdict** 生成确认卡片；如果只是想预览判定思路，用 generate_final_verdict
- 任何写入类工具（apply_check_result / apply_final_verdict）只是生成待确认的卡片，绝不代表真正写入，必须清楚告知用户"请在卡片上确认"
- 当用户需要法规依据时，调用 search_knowledge_base 搜索知识库
- 如果"待分析照片"不为"无"，说明用户刚拍了照片等待你分析，**必须主动调用 analyze_photo**（无需用户再说"帮我看看"），分析后如发现问题应直接调用 apply_check_result 生成确认卡片
- 主动提供帮助，不要被动等待用户请求

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
            "name": "list_check_items",
            "description": "列出当前检查记录中的所有检查项，包括ID、标题、顺序和当前判定结果。当用户询问某个检查项（如'第一个检查项'）时，应先调用此工具获取检查项列表和ID",
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
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "搜索知识库法规，获取相关法规依据。当用户询问法规、标准、依据时使用",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词或问题"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量，默认5",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_enterprise_history",
            "description": "获取企业历史检查记录，包括过往问题、整改情况",
            "parameters": {
                "type": "object",
                "properties": {
                    "enterprise_name": {
                        "type": "string",
                        "description": "企业名称"
                    }
                },
                "required": ["enterprise_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_template",
            "description": "为企业推荐合适的检查模板，基于企业行业、风险等级等",
            "parameters": {
                "type": "object",
                "properties": {
                    "enterprise_id": {
                        "type": "string",
                        "description": "企业ID"
                    }
                },
                "required": ["enterprise_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_photo",
            "description": "分析检查照片，识别合规问题。返回问题类型、严重程度和建议",
            "parameters": {
                "type": "object",
                "properties": {
                    "media_file_id": {
                        "type": "string",
                        "description": "照片文件ID"
                    },
                    "check_item_title": {
                        "type": "string",
                        "description": "关联的检查项标题（可选）"
                    }
                },
                "required": ["media_file_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fill_check_result",
            "description": "帮助填写检查结果建议。根据检查项信息和用户描述，给出判定建议",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "检查项ID"
                    },
                    "observation": {
                        "type": "string",
                        "description": "用户描述的检查发现"
                    }
                },
                "required": ["item_id", "observation"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_check_result",
            "description": (
                "生成检查项判定的写入建议，以确认卡片形式展示给审核员。"
                "本工具不会直接修改数据库，只有审核员在卡片上点击确认后才会真正写入。"
                "当用户已经明确表达了判定意见（如'这项不合格，问题是XX'、'这项判合格'）并希望直接记录时调用此工具，"
                "不要只是口头描述建议——应主动调用本工具生成可确认的操作卡片。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "检查项ID（record item id）"
                    },
                    "result": {
                        "type": "string",
                        "enum": ["pass", "fail", "na"],
                        "description": "判定结果：pass(合格)/fail(不合格)/na(不适用)"
                    },
                    "problem_description": {
                        "type": "string",
                        "description": "问题描述（判定为不合格时应填写）"
                    },
                    "rectification_suggestion": {
                        "type": "string",
                        "description": "整改建议（可选）"
                    }
                },
                "required": ["item_id", "result"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_final_verdict",
            "description": (
                "生成整份检查记录的最终判定写入建议，以确认卡片形式展示给审核员。"
                "本工具不会直接修改数据库，只有审核员点击确认后才会真正写入。"
                "当用户要求'生成最终判定'并希望直接记录结论时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "record_id": {
                        "type": "string",
                        "description": "检查记录ID"
                    },
                    "verdict": {
                        "type": "string",
                        "enum": ["pass", "partial_pass", "fail"],
                        "description": "最终判定：pass(合格)/partial_pass(基本合格)/fail(不合格)"
                    },
                    "comment": {
                        "type": "string",
                        "description": "总体评价说明"
                    }
                },
                "required": ["record_id", "verdict"]
            }
        }
    }
]

MAX_TOOL_ROUNDS = 5


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
        user_id: Optional[str] = None,
    ) -> AsyncGenerator[dict, None]:
        import time

        context_info = await self._build_context(context, db)

        system_prompt = AGENT_SYSTEM_PROMPT.format(
            enterprise_name=context_info.get("enterprise_name", "未知企业"),
            template_name=context_info.get("template_name", "未知模板"),
            record_id=context_info.get("record_id", ""),
            current_item_title=context_info.get("current_item_title", "无"),
            check_method=context_info.get("check_method", "未指定"),
            legal_basis=context_info.get("legal_basis", "未指定"),
            media_hint=(
                f"照片ID {context.get('media_file_id')}（用户刚拍摄/上传，尚未分析）"
                if context.get("media_file_id") else "无"
            ),
        )

        messages = [{"role": "system", "content": system_prompt}]

        for msg in conversation[-10:]:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })

        messages.append({"role": "user", "content": message})

        start_time = time.monotonic()
        total_tokens = 0
        full_response_text = ""
        error_text: Optional[str] = None

        try:
            for round_idx in range(MAX_TOOL_ROUNDS):
                is_last_round = round_idx == MAX_TOOL_ROUNDS - 1

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=None if is_last_round else TOOLS,
                    tool_choice="auto" if not is_last_round else None,
                    max_tokens=settings.LLM_MAX_TOKENS,
                    temperature=settings.LLM_TEMPERATURE,
                    stream=True,
                )

                tool_calls_buffer = {}
                had_tool_calls = False
                assistant_text = ""

                async for chunk in response:
                    if not chunk.choices:
                        if getattr(chunk, "usage", None):
                            total_tokens += chunk.usage.total_tokens or 0
                        continue

                    delta = chunk.choices[0].delta

                    if delta.content:
                        assistant_text += delta.content
                        full_response_text += delta.content
                        yield {"type": "content", "content": delta.content}

                    if delta.tool_calls:
                        had_tool_calls = True
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

                if not had_tool_calls:
                    # Model answered directly with no tool calls - we're done.
                    break

                # Replay the assistant turn (with tool calls) into history, then
                # execute every requested tool and feed results back for the next round.
                tool_call_entries = []
                for idx in sorted(tool_calls_buffer.keys()):
                    tool_call = tool_calls_buffer[idx]
                    tool_call_entries.append(tool_call)

                messages.append({
                    "role": "assistant",
                    "content": assistant_text or None,
                    "tool_calls": [{
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"]
                        }
                    } for tc in tool_call_entries]
                })

                for tool_call in tool_call_entries:
                    tool_name = tool_call["function"]["name"]
                    try:
                        tool_args = json.loads(tool_call["function"]["arguments"] or "{}")
                    except json.JSONDecodeError:
                        tool_args = {}

                    yield {"type": "tool_call", "tool": tool_name, "status": "calling"}

                    tool_result = await self._execute_tool(
                        tool_name, tool_args, context, db
                    )

                    if isinstance(tool_result, dict) and tool_result.get("type") == "action_proposal":
                        yield tool_result
                    else:
                        yield {"type": "tool_result", "tool": tool_name, "status": "done"}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(tool_result, ensure_ascii=False)
                    })

            yield {"type": "done", "content": ""}

        except Exception as e:
            print(f"[Agent] Stream error: {e}")
            error_text = str(e)
            yield {"type": "error", "content": error_text}

        finally:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            try:
                await self._log_call(
                    db=db,
                    user_id=user_id,
                    record_id=context_info.get("record_id"),
                    prompt=message,
                    response=full_response_text,
                    tokens_used=total_tokens,
                    duration_ms=duration_ms,
                    error_text=error_text,
                )
            except Exception as log_err:
                print(f"[Agent] Failed to write LLMCallLog: {log_err}")

    async def _log_call(
        self,
        db: AsyncSession,
        user_id: Optional[str],
        record_id: Optional[str],
        prompt: str,
        response: str,
        tokens_used: int,
        duration_ms: int,
        error_text: Optional[str],
    ) -> None:
        from app.models.audit import LLMCallLog

        log = LLMCallLog(
            user_id=user_id,
            record_id=record_id or None,
            call_type="agent_chat",
            prompt=prompt,
            response=response,
            model=self.model,
            tokens_used=tokens_used or None,
            duration_ms=duration_ms,
            is_success="false" if error_text else "true",
            error_msg=error_text,
        )
        db.add(log)
        await db.commit()

    async def _build_context(self, context: dict, db: AsyncSession) -> dict:
        result = {
            "enterprise_name": "未知企业",
            "template_name": "未知模板",
            "current_item_title": "无",
            "check_method": "未指定",
            "legal_basis": "未指定",
            "record_id": context.get("record_id", ""),
            "enterprise_id": context.get("enterprise_id", ""),
        }

        record_id = context.get("record_id")
        if record_id:
            stmt = select(InspectionRecord).where(InspectionRecord.id == record_id)
            db_result = await db.execute(stmt)
            record = db_result.scalar_one_or_none()
            if record:
                result["template_name"] = getattr(record, 'template_name', '未知模板') or "未知模板"
                result["enterprise_name"] = record.enterprise_name or "未知企业"
                result["enterprise_id"] = str(record.enterprise_id) if record.enterprise_id else ""

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
        tool_handlers = {
            "list_check_items": self._tool_list_check_items,
            "get_check_item_details": self._tool_get_check_item_details,
            "get_inspection_summary": self._tool_get_inspection_summary,
            "generate_final_verdict": self._tool_generate_final_verdict,
            "search_knowledge_base": self._tool_search_knowledge_base,
            "get_enterprise_history": self._tool_get_enterprise_history,
            "recommend_template": self._tool_recommend_template,
            "analyze_photo": self._tool_analyze_photo,
            "fill_check_result": self._tool_fill_check_result,
            "apply_check_result": self._tool_apply_check_result,
            "apply_final_verdict": self._tool_apply_final_verdict,
        }

        handler = tool_handlers.get(tool_name)
        if handler:
            return await handler(args, context, db)
        return {"error": f"Unknown tool: {tool_name}"}

    async def _tool_list_check_items(
        self,
        args: dict,
        context: dict,
        db: AsyncSession,
    ) -> dict:
        record_id = args.get("record_id") or context.get("record_id")

        if not record_id:
            return {"error": "未指定检查记录ID"}

        result = await db.execute(
            select(InspectionRecordItem)
            .where(InspectionRecordItem.record_id == record_id)
            .order_by(InspectionRecordItem.recorded_at)
        )
        items = result.scalars().all()

        if not items:
            return {"error": "检查记录无检查项", "items": []}

        items_list = []
        for idx, item in enumerate(items, 1):
            radio = item.radio_value
            if radio == "pass":
                result_text = "合格"
            elif radio == "fail":
                result_text = "不合格"
            elif radio == "na":
                result_text = "不适用"
            else:
                result_text = "未检查"

            items_list.append({
                "index": idx,
                "id": str(item.id),
                "title": item.item_title,
                "result": result_text,
            })

        return {
            "total": len(items_list),
            "items": items_list,
        }

    async def _tool_get_check_item_details(
        self,
        args: dict,
        context: dict,
        db: AsyncSession,
    ) -> dict:
        item_id = args.get("item_id") or context.get("current_item_id")

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
        args: dict,
        context: dict,
        db: AsyncSession,
    ) -> dict:
        record_id = args.get("record_id")
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
        args: dict,
        context: dict,
        db: AsyncSession,
    ) -> dict:
        record_id = args.get("record_id")
        summary = await self._tool_get_inspection_summary({"record_id": record_id}, context, db)

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

    async def _tool_search_knowledge_base(
        self,
        args: dict,
        context: dict,
        db: AsyncSession,
    ) -> dict:
        """Search knowledge base for relevant regulations."""
        query = args.get("query", "")
        top_k = args.get("top_k", 5)

        if not query:
            return {"error": "请提供搜索关键词"}

        results = await rag_service.search_knowledge(query, db, top_k=top_k)

        if not results:
            return {
                "query": query,
                "results": [],
                "message": "未找到相关法规"
            }

        return {
            "query": query,
            "results": results,
            "total": len(results)
        }

    async def _tool_get_enterprise_history(
        self,
        args: dict,
        context: dict,
        db: AsyncSession,
    ) -> dict:
        """Get enterprise inspection history."""
        enterprise_name = args.get("enterprise_name", "")

        if not enterprise_name:
            return {"error": "请提供企业名称"}

        # Find enterprise
        result = await db.execute(
            select(Enterprise).where(Enterprise.name == enterprise_name)
        )
        enterprise = result.scalar_one_or_none()

        if not enterprise:
            return {"error": f"未找到企业: {enterprise_name}"}

        # Get inspection records
        from app.models.task import InspectionTask

        stmt = (
            select(InspectionTask)
            .where(InspectionTask.enterprise_id == enterprise.id)
            .order_by(InspectionTask.created_at.desc())
            .limit(5)
        )
        result = await db.execute(stmt)
        tasks = result.scalars().all()

        history = []
        for task in tasks:
            history.append({
                "task_id": str(task.id),
                "task_no": task.task_no,
                "title": task.title,
                "status": task.status,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            })

        return {
            "enterprise_name": enterprise_name,
            "enterprise_id": str(enterprise.id),
            "risk_level": enterprise.risk_level,
            "history": history,
            "total_inspections": len(history)
        }

    async def _tool_recommend_template(
        self,
        args: dict,
        context: dict,
        db: AsyncSession,
    ) -> dict:
        """Recommend templates for an enterprise."""
        enterprise_id = args.get("enterprise_id") or context.get("enterprise_id")

        if not enterprise_id:
            return {"error": "请提供企业ID"}

        recommendations = await template_recommendation_service.recommend_templates(
            enterprise_id, db, top_k=3
        )

        if not recommendations:
            return {
                "enterprise_id": enterprise_id,
                "recommendations": [],
                "message": "未找到合适的模板"
            }

        return {
            "enterprise_id": enterprise_id,
            "recommendations": recommendations
        }

    async def generate_briefing(
        self,
        enterprise_id: str,
        db: AsyncSession,
    ) -> dict:
        """Phase 4: 检查前准备简报。

        编排已有能力（企业历史 + 上次遗留问题 + 知识库检索）+ 一次 LLM 综合调用，
        生成审核员出发前可以直接看的简报。复用现有查询逻辑，不重复造轮子；
        与 audit_agent.prepare_audit 的差异是：这里面向"简单检查"场景（enterprise + 历史记录），
        不依赖 AuditProject（认证审核项目）。
        """
        enterprise = await db.get(Enterprise, enterprise_id)
        if not enterprise:
            return {"error": "企业不存在"}

        records_result = await db.execute(
            select(InspectionRecord)
            .where(InspectionRecord.enterprise_id == enterprise_id)
            .where(InspectionRecord.status == "submitted")
            .order_by(InspectionRecord.inspection_date.desc())
            .limit(3)
        )
        recent_records = records_result.scalars().all()

        outstanding_issues = []
        for record in recent_records:
            items_result = await db.execute(
                select(InspectionRecordItem)
                .where(InspectionRecordItem.record_id == record.id)
                .where(InspectionRecordItem.radio_value == "fail")
            )
            for item in items_result.scalars().all():
                outstanding_issues.append({
                    "date": record.inspection_date.strftime("%Y-%m-%d") if record.inspection_date else "",
                    "title": item.item_title,
                    "problem": item.problem_description,
                    "rectification": item.rectification_suggestion,
                })

        kb_query = f"{enterprise.enterprise_type or ''} {enterprise.name} 检查要点".strip()
        kb_results = await rag_service.search_knowledge(kb_query, db, top_k=5)

        history_summary = "无历史检查记录" if not recent_records else "\n".join(
            f"- {r.inspection_date.strftime('%Y-%m-%d') if r.inspection_date else '未知日期'}："
            f"{ {'pass': '合格', 'fail': '不合格', 'partial_pass': '基本合格'}.get(r.overall_result, '未判定') }"
            for r in recent_records
        )
        issues_summary = "无遗留问题" if not outstanding_issues else "\n".join(
            f"- {i['title']}：{i['problem'] or '无描述'}" for i in outstanding_issues[:8]
        )
        regs_summary = "未检索到相关法规" if not kb_results else "\n".join(
            f"- {r.get('title', '')}: {r.get('content', '')[:100]}" for r in kb_results[:5]
        )

        prompt = f"""你是资深检查专家，请为即将进行的现场检查生成一份简明的"检查准备简报"。

企业信息：
- 企业名称：{enterprise.name}
- 行业类型：{enterprise.enterprise_type or '未知'}
- 风险等级：{enterprise.risk_level or '未知'}

历史检查记录：
{history_summary}

历史遗留问题（近3次检查中的不合格项）：
{issues_summary}

相关法规参考：
{regs_summary}

请生成一份简报，包含：
1. 企业概况一句话总结
2. 重点关注清单（3-5条具体可操作的检查要点，优先针对历史遗留问题）
3. 需要携带/核对的法规依据

用简洁的要点式语言，适合审核员出发前快速阅读，不要写成正式公文。直接输出简报正文（可用Markdown加粗/列表），不要输出JSON。"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
                temperature=0.5,
            )
            briefing_text = response.choices[0].message.content or ""
        except Exception as e:
            briefing_text = f"简报生成失败：{str(e)}"

        return {
            "enterprise_id": str(enterprise.id),
            "enterprise_name": enterprise.name,
            "risk_level": enterprise.risk_level,
            "outstanding_issues": outstanding_issues,
            "briefing_text": briefing_text,
        }

    async def _tool_analyze_photo(
        self,
        args: dict,
        context: dict,
        db: AsyncSession,
    ) -> dict:
        """Analyze a photo for compliance issues."""
        media_file_id = args.get("media_file_id") or context.get("media_file_id")
        check_item_title = args.get("check_item_title")

        if not media_file_id:
            return {"error": "请提供照片文件ID"}

        result = await multimodal_service.analyze_photo(
            media_file_id, db,
            analysis_type="compliance",
            check_item_title=check_item_title
        )

        if "error" in result:
            return result

        return {
            "media_file_id": media_file_id,
            "description": result.get("description", ""),
            "issues": result.get("issues", []),
            "compliance_status": result.get("compliance_status"),
            "confidence": result.get("confidence", 0.5),
            "recommendations": result.get("recommendations", [])
        }

    async def _tool_fill_check_result(
        self,
        args: dict,
        context: dict,
        db: AsyncSession,
    ) -> dict:
        """Help fill check result based on observation."""
        item_id = args.get("item_id") or context.get("current_item_id")
        observation = args.get("observation", "")

        if not item_id:
            return {"error": "请提供检查项ID"}

        if not observation:
            return {"error": "请描述您的检查发现"}

        # Get item details
        item = await db.get(InspectionRecordItem, item_id)
        if not item:
            return {"error": "检查项不存在"}

        # Use LLM to analyze and suggest result
        prompt = f"""根据检查员的观察，建议检查结果。

检查项：{item.item_title}
检查方法：{item.item_check_method or '未指定'}
法规依据：{item.item_legal_basis or '未指定'}

检查员观察：{observation}

请分析并建议：
1. 判定结果（合格/不合格/不适用）
2. 问题描述（如有）
3. 简要说明

以JSON格式输出：
{{
    "suggested_result": "pass/fail/na",
    "problem_description": "问题描述（如无问题可留空）",
    "reasoning": "判定理由"
}}
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.3,
            )

            import re
            content = response.choices[0].message.content or ""
            json_match = re.search(r'\{[\s\S]*\}', content)

            if json_match:
                result = json.loads(json_match.group())
                result["item_id"] = item_id
                result["item_title"] = item.item_title
                return result
            else:
                return {
                    "item_id": item_id,
                    "item_title": item.item_title,
                    "suggested_result": "unknown",
                    "reasoning": content
                }

        except Exception as e:
            return {"error": f"分析失败: {str(e)}"}

    async def _tool_apply_check_result(
        self,
        args: dict,
        context: dict,
        db: AsyncSession,
    ) -> dict:
        """Build a check-result write proposal. Does NOT write to the database -
        the frontend renders this as a confirmation card, and only calls the real
        write endpoint (POST /api/records/{record_id}/items) after the inspector
        clicks '采纳'."""
        item_id = args.get("item_id") or context.get("current_item_id")
        result = args.get("result")
        problem_description = args.get("problem_description", "")
        rectification_suggestion = args.get("rectification_suggestion", "")

        if not item_id:
            return {"error": "请提供检查项ID"}
        if result not in ("pass", "fail", "na"):
            return {"error": "判定结果必须是 pass/fail/na"}

        item = await db.get(InspectionRecordItem, item_id)
        if not item:
            return {"error": "检查项不存在"}

        record_id = str(item.record_id) if item.record_id else context.get("record_id")

        proposal = {
            "type": "action_proposal",
            "action": "apply_check_result",
            "status": "pending",
            "title": "建议记录检查结果",
            "data": {
                "record_id": record_id,
                "item_id": str(item_id),
                "item_title": item.item_title,
                "result": result,
                "problem_description": problem_description,
                "rectification_suggestion": rectification_suggestion,
            },
        }
        return proposal

    async def _tool_apply_final_verdict(
        self,
        args: dict,
        context: dict,
        db: AsyncSession,
    ) -> dict:
        """Build a final-verdict write proposal. Does NOT write to the database -
        the frontend renders this as a confirmation card, and only calls the real
        write endpoint (PUT /api/records/{record_id}) after the inspector clicks '采纳'."""
        record_id = args.get("record_id") or context.get("record_id")
        verdict = args.get("verdict")
        comment = args.get("comment", "")

        if not record_id:
            return {"error": "未指定检查记录ID"}
        if verdict not in ("pass", "partial_pass", "fail"):
            return {"error": "最终判定必须是 pass/partial_pass/fail"}

        record = await db.get(InspectionRecord, record_id)
        if not record:
            return {"error": "检查记录不存在"}

        proposal = {
            "type": "action_proposal",
            "action": "apply_final_verdict",
            "status": "pending",
            "title": "建议记录最终判定",
            "data": {
                "record_id": str(record_id),
                "verdict": verdict,
                "comment": comment,
            },
        }
        return proposal


agent_service = AgentService()