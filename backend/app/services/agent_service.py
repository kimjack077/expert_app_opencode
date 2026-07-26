import json
from typing import Any, AsyncGenerator, Optional
from uuid import UUID

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
from app.models.audit_project import AuditPlanItem, AuditProject
from app.models.evidence_agent import AiAuditSession, AiDraftRecord
from app.services.rag_service import rag_service
from app.services.template_recommendation_service import template_recommendation_service
from app.services.multimodal_service import multimodal_service
from app.services.agent_memory_service import agent_memory_service


AGENT_SYSTEM_PROMPT = """你是EFIS系统的现场检查AI助手。你正在辅助检查员完成现场检查。

当前检查上下文（已提供）：
- 企业：{enterprise_name}
- 检查模板：{template_name}
- 检查记录ID：{record_id}
- 当前检查项：{current_item_title}
- 检查方法：{check_method}
- 法规依据：{legal_basis}
- 待分析照片：{media_hint}

当前正式审核项目上下文：
- 审核项目：{project_title}
- 项目ID：{project_id}
- 审核区域：{audit_area_name}
- 计划项ID：{plan_item_id}
- 审核会话ID：{audit_session_id}
- 认证体系：{certification_systems}

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
12. get_audit_project_context - 获取当前正式审核项目、区域、计划项和会话上下文
13. search_audit_knowledge - 同时检索全局法规和当前项目资料，项目资料严格按 project_id 隔离
14. propose_audit_evidence - 为当前正式审核会话生成证据提交确认卡片
15. propose_audit_draft_confirmation - 为当前会话的 AI 草稿生成批量确认卡片，确认后写入正式区域记录

重要规则：
- 当用户询问某个检查项（如"第一个检查项"、"第二项"等）时，**必须先调用 list_check_items 获取检查项列表和ID**，然后再调用 get_check_item_details 获取详情
- 当用户询问检查汇总时，你应该**主动调用** get_inspection_summary 工具来获取数据，不要询问用户！
- 当用户明确表达了判定意见（如"这项不合格，问题是缺少校验记录"）时，**必须调用 apply_check_result** 生成确认卡片，而不是只用文字描述——审核员需要能一键采纳
- 当用户要求"生成最终判定"且希望记录结论时，**调用 apply_final_verdict** 生成确认卡片；如果只是想预览判定思路，用 generate_final_verdict
- 任何写入类工具（apply_check_result / apply_final_verdict）只是生成待确认的卡片，绝不代表真正写入，必须清楚告知用户"请在卡片上确认"
- 当用户需要法规依据时，调用 search_knowledge_base 搜索知识库
- 如果"待分析照片"不为"无"，说明用户刚拍了照片等待你分析，**必须主动调用 analyze_photo**（无需用户再说"帮我看看"），分析后如发现问题应直接调用 apply_check_result 生成确认卡片
- 主动提供帮助，不要被动等待用户请求
- 存在项目ID时，优先使用正式审核项目工具，不得把项目计划项ID当作普通检查记录ID
- 正式审核的任何写入必须保留 project_id、audit_session_id 和 plan_item_id，并通过确认卡执行

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
            "description": "为企业推荐合适的检查模板。优先使用当前页面的企业；也可按企业ID或企业名称查询",
            "parameters": {
                "type": "object",
                "properties": {
                    "enterprise_id": {
                        "type": "string",
                        "description": "企业ID"
                    },
                    "enterprise_name": {
                        "type": "string",
                        "description": "企业名称"
                    }
                }
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

TOOLS.extend(
    [
        {
            "type": "function",
            "function": {
                "name": "get_audit_project_context",
                "description": "获取当前正式审核项目、区域、计划项、会话及待确认草稿摘要",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_audit_knowledge",
                "description": "同时检索全局法规知识库和当前项目专属资料；项目资料按 project_id 强隔离",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "法规、条款或项目资料问题"},
                        "top_k": {"type": "integer", "default": 8, "minimum": 1, "maximum": 20},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "propose_audit_evidence",
                "description": "为当前正式审核会话生成证据提交确认卡；确认后创建多条款 AI 草稿",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "完整现场证据描述"},
                        "evidence_type": {
                            "type": "string",
                            "enum": ["text", "voice", "photo", "document", "mixed"],
                            "default": "text",
                        },
                        "media_file_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                        },
                    },
                    "required": ["content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "propose_audit_draft_confirmation",
                "description": "生成当前会话 AI 草稿的批量确认卡；确认后写入 AuditAreaRecord 正式记录链",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "draft_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                        },
                        "safe_only": {
                            "type": "boolean",
                            "default": False,
                            "description": "仅确认非异常且证据充分的草稿",
                        },
                    },
                },
            },
        },
    ]
)

MAX_TOOL_ROUNDS = 5
MAX_KNOWLEDGE_SEARCHES = 2
# 单次对话的累计 token 预算。此前只有轮次上限，没有成本上限：
# 一轮里塞进超长检索结果同样会把成本推高。达到预算后强制收尾出答案。
MAX_CONVERSATION_TOKENS = 60000
# 送入模型的最近历史条数（其余省略，并在 system 消息中明确告知模型）
HISTORY_TURNS_SENT_TO_MODEL = 10
FINAL_RESPONSE_INSTRUCTION = """工具调用已结束。请仅基于已获得的工具结果，直接给出完整、准确的最终答复。
不要描述继续检索的过程，不要再次请求工具；若资料不足，必须明确说明缺少什么资料。"""
FORCE_FINAL_USER_PROMPT = (
    "请立即给出完整最终答复：基于已获得的工具结果回答用户问题，"
    "列出引用来源；禁止再次调用工具；不要只输出空内容。"
)


class AgentService:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            timeout=settings.LLM_TIMEOUT,
        )
        self.model = settings.LLM_MODEL
        self.vision_client = AsyncOpenAI(
            base_url=settings.VISION_LLM_BASE_URL,
            api_key=settings.VISION_LLM_API_KEY,
            timeout=settings.LLM_TIMEOUT,
        )
        self.vision_model = settings.VISION_LLM_MODEL

    def get_available_models(self) -> list[dict]:
        models = [
            {
                "id": self.model,
                "name": "DeepSeek V4 Flash",
                "capabilities": ["text"],
                "recommended_for": "文字问答和检查准备简报",
            },
            {
                "id": self.vision_model,
                "name": "SenseNova 6.7 Flash Lite",
                "capabilities": ["text", "vision"],
                "recommended_for": "图片识别和多模态分析",
            },
        ]

        return list({model["id"]: model for model in models}.values())

    def _resolve_model(self, model_id: Optional[str]) -> tuple[AsyncOpenAI, str] | None:
        selected_model = model_id or self.model
        if selected_model == self.model:
            return self.client, self.model
        if selected_model == self.vision_model:
            return self.vision_client, self.vision_model
        return None

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
            project_title=context_info.get("project_title", "无"),
            project_id=context_info.get("project_id", ""),
            audit_area_name=context_info.get("audit_area_name", "无"),
            plan_item_id=context_info.get("plan_item_id", ""),
            audit_session_id=context_info.get("audit_session_id", ""),
            certification_systems="、".join(
                context_info.get("certification_systems") or []
            ) or "未指定",
            media_hint=(
                f"照片ID {context.get('media_file_id')}（用户刚拍摄/上传，尚未分析）"
                if context.get("media_file_id") else "无"
            ),
        )

        messages = [{"role": "system", "content": system_prompt}]

        # 只带最近 N 轮进模型。超出部分会被丢弃——明确告知模型，
        # 避免它把「上文不存在」当成「用户没说过」而给出自相矛盾的回答。
        recent = conversation[-HISTORY_TURNS_SENT_TO_MODEL:]
        if len(conversation) > HISTORY_TURNS_SENT_TO_MODEL:
            messages.append({
                "role": "system",
                "content": (
                    f"注意：本次仅提供最近 {HISTORY_TURNS_SENT_TO_MODEL} 条对话，"
                    f"更早的 {len(conversation) - HISTORY_TURNS_SENT_TO_MODEL} 条已省略。"
                    "如需更早的信息，请明确向用户确认，不要臆测。"
                ),
            })

        for msg in recent:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })

        messages.append({"role": "user", "content": message})

        start_time = time.monotonic()
        total_tokens = 0
        full_response_text = ""
        error_text: Optional[str] = None
        knowledge_search_signatures: set[str] = set()
        knowledge_search_count = 0
        collected_tool_results: list[tuple[str, Any]] = []

        try:
            for round_idx in range(MAX_TOOL_ROUNDS):
                is_last_round = round_idx == MAX_TOOL_ROUNDS - 1
                # Only the last round forbids tools. Earlier rounds may still
                # call tools; empty final answers are recovered after the loop.
                # 预算耗尽同样强制收尾，避免单次对话成本失控。
                over_budget = total_tokens >= MAX_CONVERSATION_TOKENS
                if over_budget and round_idx > 0:
                    print(
                        f"[Agent] token budget reached ({total_tokens}), forcing final answer"
                    )
                force_final = is_last_round or over_budget

                request_messages = list(messages)
                if force_final:
                    request_messages.append(
                        {"role": "system", "content": FINAL_RESPONSE_INSTRUCTION}
                    )
                    request_messages.append(
                        {"role": "user", "content": FORCE_FINAL_USER_PROMPT}
                    )

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=request_messages,
                    tools=None if force_final else TOOLS,
                    tool_choice="auto" if not force_final else None,
                    max_tokens=settings.LLM_MAX_TOKENS,
                    temperature=settings.LLM_TEMPERATURE,
                    stream=True,
                )

                tool_calls_buffer: dict[int, dict] = {}
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

                    if delta.tool_calls and not force_final:
                        had_tool_calls = True
                        for tool_call_delta in delta.tool_calls:
                            idx = tool_call_delta.index

                            if idx not in tool_calls_buffer:
                                tool_calls_buffer[idx] = {
                                    "id": "",
                                    "function": {"name": "", "arguments": ""},
                                }

                            if tool_call_delta.id:
                                tool_calls_buffer[idx]["id"] = tool_call_delta.id
                            if tool_call_delta.function:
                                if tool_call_delta.function.name:
                                    tool_calls_buffer[idx]["function"]["name"] = (
                                        tool_call_delta.function.name
                                    )
                                if tool_call_delta.function.arguments:
                                    tool_calls_buffer[idx]["function"][
                                        "arguments"
                                    ] += tool_call_delta.function.arguments

                if not had_tool_calls:
                    # Only surface text once the turn is a final answer.
                    if not assistant_text.strip():
                        recovered = await self._recover_empty_final_answer(
                            messages=messages,
                            user_message=message,
                            collected_tool_results=collected_tool_results,
                        )
                        if recovered:
                            full_response_text += recovered
                            yield {"type": "content", "content": recovered}
                            break

                        error_text = "模型未生成最终答复"
                        yield {
                            "type": "error",
                            "content": "AI 未能生成最终答复，请稍后重试。",
                        }
                        return

                    full_response_text += assistant_text
                    yield {"type": "content", "content": assistant_text}
                    break

                # Replay the assistant turn (with tool calls) into history, then
                # execute every requested tool and feed results back for the next round.
                tool_call_entries = []
                for idx in sorted(tool_calls_buffer.keys()):
                    tool_call = tool_calls_buffer[idx]
                    if not tool_call["function"]["name"]:
                        continue
                    if not tool_call["id"]:
                        tool_call["id"] = f"call_{round_idx}_{idx}"
                    tool_call_entries.append(tool_call)

                if not tool_call_entries:
                    recovered = await self._recover_empty_final_answer(
                        messages=messages,
                        user_message=message,
                        collected_tool_results=collected_tool_results,
                    )
                    if recovered:
                        full_response_text += recovered
                        yield {"type": "content", "content": recovered}
                        break
                    error_text = "模型返回空的工具调用"
                    yield {
                        "type": "error",
                        "content": "AI 未能生成最终答复，请稍后重试。",
                    }
                    return

                messages.append({
                    "role": "assistant",
                    "content": assistant_text or None,
                    "tool_calls": [{
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"] or "{}",
                        },
                    } for tc in tool_call_entries],
                })

                for tool_call in tool_call_entries:
                    tool_name = tool_call["function"]["name"]
                    try:
                        tool_args = json.loads(tool_call["function"]["arguments"] or "{}")
                    except json.JSONDecodeError:
                        tool_args = {}

                    yield {"type": "tool_call", "tool": tool_name, "status": "calling"}

                    if tool_name in {"search_knowledge_base", "search_audit_knowledge"}:
                        search_signature = json.dumps(
                            tool_args, ensure_ascii=False, sort_keys=True
                        )
                        if search_signature in knowledge_search_signatures:
                            tool_result = {
                                "message": "相同的知识库检索已执行，请基于已有结果直接回答。",
                                "retryable": False,
                            }
                        elif knowledge_search_count >= MAX_KNOWLEDGE_SEARCHES:
                            tool_result = {
                                "message": "已达到本次问答的知识库检索次数上限，请基于已有结果直接回答。",
                                "retryable": False,
                            }
                        else:
                            knowledge_search_signatures.add(search_signature)
                            knowledge_search_count += 1
                            tool_result = await self._execute_tool(
                                tool_name, tool_args, context, db
                            )
                    else:
                        tool_result = await self._execute_tool(
                            tool_name, tool_args, context, db
                        )

                    tool_result = self._compact_tool_result(tool_name, tool_result)
                    collected_tool_results.append((tool_name, tool_result))

                    if isinstance(tool_result, dict) and tool_result.get("type") == "action_proposal":
                        yield tool_result
                    else:
                        yield {"type": "tool_result", "tool": tool_name, "status": "done"}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(tool_result, ensure_ascii=False, default=str),
                    })

            if not full_response_text.strip():
                recovered = await self._recover_empty_final_answer(
                    messages=messages,
                    user_message=message,
                    collected_tool_results=collected_tool_results,
                )
                if recovered:
                    full_response_text = recovered
                    yield {"type": "content", "content": recovered}
                else:
                    error_text = "工具轮次结束后未生成最终答复"
                    yield {
                        "type": "error",
                        "content": "AI 未能生成最终答复，请稍后重试。",
                    }
                    return

            yield {"type": "done", "content": ""}

        except Exception as e:
            print(f"[Agent] Stream error: {type(e).__name__}: {e}")
            error_text = str(e)
            yield {
                "type": "error",
                "content": "AI 助手暂时无法完成这次请求，请换一种说法或稍后重试。",
            }

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
        call_type: str = "agent_chat",
        model: Optional[str] = None,
    ) -> None:
        from app.models.audit import LLMCallLog

        log = LLMCallLog(
            user_id=user_id,
            record_id=record_id or None,
            call_type=call_type,
            prompt=prompt,
            response=response,
            model=model or self.model,
            tokens_used=tokens_used or None,
            duration_ms=duration_ms,
            is_success="false" if error_text else "true",
            error_msg=error_text,
        )
        db.add(log)
        await db.commit()

    @staticmethod
    def _compact_tool_result(tool_name: str, tool_result: Any) -> Any:
        """Shrink large retrieval payloads so the final answer turn stays reliable."""
        if not isinstance(tool_result, dict):
            return tool_result

        if tool_name not in {"search_knowledge_base", "search_audit_knowledge"}:
            return tool_result

        results = tool_result.get("results")
        if not isinstance(results, list):
            return tool_result

        compact_results = []
        for item in results[:8]:
            if not isinstance(item, dict):
                compact_results.append(item)
                continue
            content = item.get("content") or item.get("text") or ""
            compact_results.append(
                {
                    "source_scope": item.get("source_scope"),
                    "document_id": item.get("document_id"),
                    "document_title": item.get("document_title")
                    or item.get("file_name")
                    or item.get("source"),
                    "file_name": item.get("file_name"),
                    "similarity": item.get("similarity")
                    or item.get("score")
                    or item.get("relevance"),
                    "content": str(content)[:500],
                }
            )

        return {
            **tool_result,
            "results": compact_results,
            "result_count": len(results),
        }

    async def _recover_empty_final_answer(
        self,
        *,
        messages: list,
        user_message: str,
        collected_tool_results: list[tuple[str, Any]],
    ) -> Optional[str]:
        """Retry once for an empty final turn; if still empty, synthesize from tools."""
        if not collected_tool_results:
            return None

        try:
            retry_messages = list(messages) + [
                {"role": "system", "content": FINAL_RESPONSE_INSTRUCTION},
                {
                    "role": "user",
                    "content": (
                        f"用户原问题：{user_message}\n\n{FORCE_FINAL_USER_PROMPT}"
                    ),
                },
            ]
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=retry_messages,
                tools=None,
                max_tokens=min(2048, settings.LLM_MAX_TOKENS),
                temperature=0.3,
                stream=False,
            )
            content = ""
            if response.choices:
                content = (response.choices[0].message.content or "").strip()
            if content:
                return content
        except Exception as exc:
            print(f"[Agent] Final-answer recovery failed: {type(exc).__name__}: {exc}")

        return self._fallback_answer_from_tools(user_message, collected_tool_results)

    @staticmethod
    def _fallback_answer_from_tools(
        user_message: str,
        collected_tool_results: list[tuple[str, Any]],
    ) -> str:
        """Deterministic answer when the model returns empty after tools."""
        lines = [
            "已完成工具调用，但模型未生成自然语言总结。以下根据工具结果直接整理：",
            "",
            f"**用户问题：** {user_message}",
            "",
        ]

        for tool_name, payload in collected_tool_results:
            if tool_name == "get_audit_project_context" and isinstance(payload, dict):
                lines.extend(
                    [
                        "## 项目上下文",
                        f"- 项目：{payload.get('project_title') or '未知'}",
                        f"- 企业：{payload.get('enterprise_name') or '未知'}",
                        f"- 区域：{payload.get('area_name') or '未设定'}",
                        f"- 认证体系：{'、'.join(payload.get('certification_systems') or []) or '未指定'}",
                        f"- 待确认草稿：{len(payload.get('pending_drafts') or [])} 条",
                        "",
                    ]
                )
                continue

            if tool_name in {"search_knowledge_base", "search_audit_knowledge"} and isinstance(
                payload, dict
            ):
                results = payload.get("results") or []
                lines.append("## 知识检索结果与引用来源")
                if payload.get("query"):
                    lines.append(f"- 检索词：{payload.get('query')}")
                if not results:
                    lines.append("- 未检索到可用资料片段。")
                    lines.append("")
                    continue
                for index, item in enumerate(results[:8], start=1):
                    if not isinstance(item, dict):
                        lines.append(f"{index}. {item}")
                        continue
                    title = (
                        item.get("document_title")
                        or item.get("file_name")
                        or item.get("source")
                        or "未命名资料"
                    )
                    scope = item.get("source_scope") or "unknown"
                    scope_label = (
                        "全局法规" if scope == "global_regulation" else "项目资料"
                    )
                    score = (
                        item.get("similarity")
                        or item.get("score")
                        or item.get("relevance")
                    )
                    score_text = ""
                    if isinstance(score, (int, float)):
                        score_text = (
                            f"，相关度 {score * 100:.0f}%"
                            if score <= 1
                            else f"，相关度 {score:.0f}"
                        )
                    excerpt = str(item.get("content") or item.get("text") or "").strip()
                    if len(excerpt) > 280:
                        excerpt = excerpt[:280] + "…"
                    lines.append(f"{index}. **[{scope_label}] {title}**{score_text}")
                    if excerpt:
                        lines.append(f"   > {excerpt}")
                lines.append("")
                continue

            if isinstance(payload, dict) and payload.get("error"):
                lines.append(f"## 工具 `{tool_name}`")
                lines.append(f"- 错误：{payload.get('error')}")
                lines.append("")

        lines.append(
            "如需更完整的自然语言分析，请再试一次或换一种问法（例如先问「当前项目资料清单」）。"
        )
        return "\n".join(lines)

    async def _build_context(self, context: dict, db: AsyncSession) -> dict:
        result = {
            "enterprise_name": "未知企业",
            "template_name": "未知模板",
            "current_item_title": "无",
            "check_method": "未指定",
            "legal_basis": "未指定",
            "record_id": context.get("record_id", ""),
            "enterprise_id": context.get("enterprise_id", ""),
            "project_title": "无",
            "project_id": "",
            "audit_area_name": "无",
            "plan_item_id": "",
            "audit_session_id": "",
            "certification_systems": [],
        }

        project_id = self._normalize_uuid(context.get("project_id"))
        session_id = self._normalize_uuid(context.get("audit_session_id"))
        plan_item_id = self._normalize_uuid(context.get("plan_item_id"))

        if session_id:
            session = await db.get(AiAuditSession, session_id)
            if session and (not project_id or str(session.project_id) == project_id):
                project_id = str(session.project_id)
                result["audit_session_id"] = str(session.id)
                session_context = session.context_snapshot or {}
                plan_item_id = plan_item_id or self._normalize_uuid(
                    session_context.get("plan_item_id")
                )
                result["audit_area_name"] = (
                    session_context.get("area_name") or result["audit_area_name"]
                )

        if project_id:
            project_result = await db.execute(
                select(AuditProject)
                .options(selectinload(AuditProject.enterprise))
                .where(AuditProject.id == project_id)
            )
            project = project_result.scalar_one_or_none()
            if project:
                result["project_id"] = str(project.id)
                result["project_title"] = project.title
                result["certification_systems"] = project.certification_systems or []
                if project.enterprise:
                    result["enterprise_name"] = project.enterprise.name
                    result["enterprise_id"] = str(project.enterprise.id)

        if plan_item_id:
            plan_item = await db.get(AuditPlanItem, plan_item_id)
            if plan_item and (not project_id or str(plan_item.project_id) == project_id):
                result["plan_item_id"] = str(plan_item.id)
                result["audit_area_name"] = plan_item.area_name
                result["certification_systems"] = (
                    plan_item.certification_systems
                    or result["certification_systems"]
                )

        record_id = self._normalize_uuid(context.get("record_id"))
        if record_id:
            stmt = select(InspectionRecord).where(InspectionRecord.id == record_id)
            db_result = await db.execute(stmt)
            record = db_result.scalar_one_or_none()
            if record:
                result["template_name"] = getattr(record, 'template_name', '未知模板') or "未知模板"
                result["enterprise_name"] = record.enterprise_name or "未知企业"
                result["enterprise_id"] = str(record.enterprise_id) if record.enterprise_id else ""

        enterprise_id = self._normalize_uuid(
            result.get("enterprise_id") or context.get("enterprise_id")
        )
        if enterprise_id:
            enterprise = await db.get(Enterprise, enterprise_id)
            if enterprise:
                result["enterprise_name"] = enterprise.name
                result["enterprise_id"] = str(enterprise.id)

        current_item_id = self._normalize_uuid(context.get("current_item_id"))
        if current_item_id:
            item = await db.get(InspectionRecordItem, current_item_id)
            if item:
                result["current_item_title"] = item.item_title or "未知检查项"
                result["check_method"] = item.item_check_method or "未指定"
                result["legal_basis"] = item.item_legal_basis or "未指定"

        return result

    @staticmethod
    def _normalize_uuid(value: object) -> Optional[str]:
        if not value:
            return None
        try:
            return str(UUID(str(value)))
        except (TypeError, ValueError, AttributeError):
            return None

    async def _resolve_enterprise(
        self,
        args: dict,
        context: dict,
        db: AsyncSession,
    ) -> Optional[Enterprise]:
        raw_context_id = context.get("enterprise_id")
        raw_argument_id = args.get("enterprise_id")
        enterprise_id = self._normalize_uuid(raw_context_id) or self._normalize_uuid(
            raw_argument_id
        )
        if enterprise_id:
            enterprise = await db.get(Enterprise, enterprise_id)
            if enterprise:
                return enterprise

        enterprise_names = [
            args.get("enterprise_name"),
            raw_argument_id if not self._normalize_uuid(raw_argument_id) else None,
        ]
        for enterprise_name in enterprise_names:
            if not enterprise_name:
                continue
            result = await db.execute(
                select(Enterprise).where(Enterprise.name == str(enterprise_name))
            )
            enterprise = result.scalar_one_or_none()
            if enterprise:
                return enterprise

        return None

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
            "get_audit_project_context": self._tool_get_audit_project_context,
            "search_audit_knowledge": self._tool_search_audit_knowledge,
            "propose_audit_evidence": self._tool_propose_audit_evidence,
            "propose_audit_draft_confirmation": self._tool_propose_audit_draft_confirmation,
        }

        handler = tool_handlers.get(tool_name)
        if not handler:
            return {"error": "暂不支持这项操作"}

        try:
            return await handler(args, context, db)
        except Exception as exc:
            print(f"[Agent] Tool {tool_name} failed: {type(exc).__name__}: {exc}")
            try:
                await db.rollback()
            except Exception as rollback_exc:
                print(
                    f"[Agent] Tool rollback failed: "
                    f"{type(rollback_exc).__name__}: {rollback_exc}"
                )
            return {
                "error": "工具执行失败，请确认对象后重试或换一种说法",
                "retryable": True,
            }

    async def _tool_list_check_items(
        self,
        args: dict,
        context: dict,
        db: AsyncSession,
    ) -> dict:
        record_id = self._normalize_uuid(
            context.get("record_id") or args.get("record_id")
        )

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
        item_id = self._normalize_uuid(
            context.get("current_item_id") or args.get("item_id")
        )

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
        record_id = self._normalize_uuid(
            context.get("record_id") or args.get("record_id")
        )
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
        enterprise = await self._resolve_enterprise(args, context, db)

        if not enterprise:
            return {"error": "未找到对应企业，请提供准确的企业名称"}

        stmt = (
            select(InspectionRecord)
            .options(selectinload(InspectionRecord.items))
            .where(InspectionRecord.enterprise_id == enterprise.id)
            .where(InspectionRecord.status == "submitted")
            .order_by(InspectionRecord.inspection_date.desc())
            .limit(5)
        )
        result = await db.execute(stmt)
        records = result.scalars().all()

        history = []
        for record in records:
            issues = [
                {
                    "title": item.item_title,
                    "problem": item.problem_description,
                    "rectification": item.rectification_suggestion,
                }
                for item in record.items
                if item.radio_value == "fail" or item.result == "fail"
            ]
            history.append({
                "record_id": str(record.id),
                "inspection_date": (
                    record.inspection_date.isoformat()
                    if record.inspection_date else None
                ),
                "status": record.status,
                "overall_result": record.overall_result,
                "issues": issues,
            })

        return {
            "enterprise_name": enterprise.name,
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
        enterprise = await self._resolve_enterprise(args, context, db)
        if not enterprise:
            return {"error": "未找到对应企业，请提供准确的企业名称"}

        recommendations = await template_recommendation_service.recommend_templates(
            str(enterprise.id), db, top_k=3
        )

        if not recommendations:
            return {
                "enterprise_id": str(enterprise.id),
                "recommendations": [],
                "message": "未找到合适的模板"
            }

        return {
            "enterprise_id": str(enterprise.id),
            "recommendations": recommendations
        }

    async def _prepare_briefing(
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

        # 长期记忆（#5）：带入这家企业既往审核沉淀的记忆（如某条款反复不符合）
        memory_text = await agent_memory_service.recall_text(db, enterprise.id, limit=5)
        memory_block = f"\n{memory_text}\n" if memory_text else ""

        prompt = f"""你是资深检查专家，请为即将进行的现场检查生成一份简明的"检查准备简报"。

企业信息：
- 企业名称：{enterprise.name}
- 行业类型：{enterprise.enterprise_type or '未知'}
- 风险等级：{enterprise.risk_level or '未知'}

历史检查记录：
{history_summary}

历史遗留问题（近3次检查中的不合格项）：
{issues_summary}
{memory_block}
相关法规参考：
{regs_summary}

请生成一份简报，包含：
1. 企业概况一句话总结
2. 重点关注清单（3-5条具体可操作的检查要点，优先针对历史遗留问题）
3. 需要携带/核对的法规依据

用简洁的要点式语言，适合审核员出发前快速阅读，不要写成正式公文。直接输出简报正文（可用Markdown加粗/列表），不要输出JSON。"""

        return {
            "enterprise_id": str(enterprise.id),
            "enterprise_name": enterprise.name,
            "risk_level": enterprise.risk_level,
            "outstanding_issues": outstanding_issues,
            "prompt": prompt,
        }

    async def generate_briefing(
        self,
        enterprise_id: str,
        db: AsyncSession,
        model_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict:
        briefing = await self._prepare_briefing(enterprise_id, db)
        if "error" in briefing:
            return briefing

        resolved_model = self._resolve_model(model_id)
        if not resolved_model:
            return {"error": "不支持所选 AI 模型", "status_code": 400}

        client, selected_model = resolved_model
        max_tokens = 4096 if selected_model == self.vision_model else 1500

        # 简报此前完全不写 LLMCallLog，导致这条链路的用量与失败率在成本
        # 统计里是盲区。统一记账。
        start_time = time.monotonic()
        briefing_text = ""
        tokens_used = 0
        error_text: Optional[str] = None
        try:
            response = await client.chat.completions.create(
                model=selected_model,
                messages=[{"role": "user", "content": briefing["prompt"]}],
                max_tokens=max_tokens,
                temperature=0.5,
            )
            briefing_text = response.choices[0].message.content or ""
            tokens_used = getattr(getattr(response, "usage", None), "total_tokens", 0) or 0
            if not briefing_text.strip():
                error_text = "empty briefing content"
                return {
                    "error": "所选模型未返回简报内容，请切换模型后重试",
                    "status_code": 502,
                }
        except Exception as e:
            error_text = f"{type(e).__name__}: {e}"
            print(f"[Agent] Briefing generation failed: {type(e).__name__}")
            return {
                "error": "AI 简报服务暂时不可用，请切换模型或稍后重试",
                "status_code": 502,
            }
        finally:
            try:
                await self._log_call(
                    db=db,
                    user_id=user_id,
                    record_id=None,
                    prompt=briefing["prompt"],
                    response=briefing_text,
                    tokens_used=tokens_used,
                    duration_ms=int((time.monotonic() - start_time) * 1000),
                    error_text=error_text,
                    call_type="agent_briefing",
                    model=selected_model,
                )
            except Exception as log_err:
                print(f"[Agent] Failed to write briefing LLMCallLog: {log_err}")

        return {
            key: value
            for key, value in briefing.items()
            if key != "prompt"
        } | {
            "briefing_text": briefing_text,
            "model": selected_model,
        }

    async def generate_briefing_stream(
        self,
        enterprise_id: str,
        db: AsyncSession,
        model_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> AsyncGenerator[dict, None]:
        briefing = await self._prepare_briefing(enterprise_id, db)
        if "error" in briefing:
            yield {
                "type": "error",
                "content": briefing["error"],
                "status_code": briefing.get("status_code", 404),
            }
            return

        resolved_model = self._resolve_model(model_id)
        if not resolved_model:
            yield {"type": "error", "content": "不支持所选 AI 模型", "status_code": 400}
            return

        client, selected_model = resolved_model
        max_tokens = 4096 if selected_model == self.vision_model else 1500
        metadata = {
            key: value
            for key, value in briefing.items()
            if key != "prompt"
        }
        metadata["model"] = selected_model
        yield {"type": "metadata", "data": metadata}

        has_content = False
        start_time = time.monotonic()
        collected_text = ""
        stream_tokens = 0
        stream_error: Optional[str] = None
        try:
            stream = await client.chat.completions.create(
                model=selected_model,
                messages=[{"role": "user", "content": briefing["prompt"]}],
                max_tokens=max_tokens,
                temperature=0.5,
                stream=True,
            )
            async for chunk in stream:
                usage = getattr(chunk, "usage", None)
                if usage and getattr(usage, "total_tokens", None):
                    stream_tokens = usage.total_tokens
                if not chunk.choices:
                    continue
                content = chunk.choices[0].delta.content
                if content:
                    has_content = True
                    collected_text += content
                    yield {"type": "content", "content": content}
        except Exception as exc:
            stream_error = f"{type(exc).__name__}: {exc}"
            print(f"[Agent] Briefing stream failed: {type(exc).__name__}: {exc}")
            yield {
                "type": "error",
                "content": "AI 简报服务暂时不可用，请切换模型或稍后重试",
                "status_code": 502,
            }
            return
        finally:
            try:
                await self._log_call(
                    db=db,
                    user_id=user_id,
                    record_id=None,
                    prompt=briefing["prompt"],
                    response=collected_text,
                    tokens_used=stream_tokens,
                    duration_ms=int((time.monotonic() - start_time) * 1000),
                    error_text=stream_error,
                    call_type="agent_briefing_stream",
                    model=selected_model,
                )
            except Exception as log_err:
                print(f"[Agent] Failed to write briefing LLMCallLog: {log_err}")

        if not has_content:
            yield {
                "type": "error",
                "content": "所选模型未返回简报内容，请切换模型后重试",
                "status_code": 502,
            }
            return

        yield {"type": "done"}

    async def _tool_analyze_photo(
        self,
        args: dict,
        context: dict,
        db: AsyncSession,
    ) -> dict:
        """Analyze a photo for compliance issues."""
        media_file_id = self._normalize_uuid(
            context.get("media_file_id") or args.get("media_file_id")
        )
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
        item_id = self._normalize_uuid(
            context.get("current_item_id") or args.get("item_id")
        )
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
            print(f"[Agent] Result analysis failed: {type(e).__name__}: {e}")
            return {"error": "暂时无法分析检查结果，请稍后重试"}

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
        item_id = self._normalize_uuid(
            context.get("current_item_id") or args.get("item_id")
        )
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

    async def _tool_get_audit_project_context(
        self,
        args: dict,
        context: dict,
        db: AsyncSession,
    ) -> dict:
        project_id = self._normalize_uuid(context.get("project_id"))
        if not project_id:
            return {"error": "当前页面未提供正式审核项目ID"}

        context_info = await self._build_context(context, db)
        session_id = self._normalize_uuid(context.get("audit_session_id"))
        pending_drafts: list[dict] = []
        if session_id:
            rows = await db.execute(
                select(AiDraftRecord).where(
                    AiDraftRecord.project_id == project_id,
                    AiDraftRecord.session_id == session_id,
                    AiDraftRecord.status == "draft",
                )
            )
            pending_drafts = [
                {
                    "id": str(draft.id),
                    "clause_no": draft.primary_clause_no,
                    "evaluation": draft.evaluation,
                    "quality": draft.quality or {},
                    "confidence": float(draft.confidence or 0),
                }
                for draft in rows.scalars().all()
            ]
        return {
            "project_id": context_info.get("project_id"),
            "project_title": context_info.get("project_title"),
            "enterprise_name": context_info.get("enterprise_name"),
            "plan_item_id": context_info.get("plan_item_id"),
            "area_name": context_info.get("audit_area_name"),
            "audit_session_id": context_info.get("audit_session_id"),
            "certification_systems": context_info.get("certification_systems"),
            "pending_drafts": pending_drafts,
        }

    async def _tool_search_audit_knowledge(
        self,
        args: dict,
        context: dict,
        db: AsyncSession,
    ) -> dict:
        project_id = self._normalize_uuid(context.get("project_id"))
        query = str(args.get("query") or "").strip()
        if not project_id:
            return {"error": "当前页面未提供正式审核项目ID"}
        if not query:
            return {"error": "请输入要检索的法规或项目资料问题"}
        try:
            top_k = max(1, min(20, int(args.get("top_k") or 8)))
        except (TypeError, ValueError):
            top_k = 8

        from app.services.project_knowledge_service import project_knowledge_service

        results = await project_knowledge_service.search_combined(
            db, UUID(project_id), query, top_k
        )
        return {"project_id": project_id, "query": query, "results": results}

    async def _tool_propose_audit_evidence(
        self,
        args: dict,
        context: dict,
        db: AsyncSession,
    ) -> dict:
        project_id = self._normalize_uuid(context.get("project_id"))
        session_id = self._normalize_uuid(context.get("audit_session_id"))
        content = str(args.get("content") or "").strip()
        if not project_id or not session_id:
            return {"error": "正式审核证据需要项目ID和审核会话ID"}
        if not content:
            return {"error": "现场证据内容不能为空"}

        session = (
            await db.execute(
                select(AiAuditSession).where(
                    AiAuditSession.id == session_id,
                    AiAuditSession.project_id == project_id,
                    AiAuditSession.status == "active",
                )
            )
        ).scalar_one_or_none()
        if not session:
            return {"error": "当前项目审核会话不存在或已结束"}

        media_ids = [
            value
            for value in (
                self._normalize_uuid(item) for item in (args.get("media_file_ids") or [])
            )
            if value
        ]
        session_context = session.context_snapshot or {}
        payload = {
            "content": content,
            "evidence_type": args.get("evidence_type") or (
                "mixed" if media_ids else "text"
            ),
            "media_file_ids": media_ids,
            "candidate_item_ids": [],
            "source_metadata": {
                "source": "web_agent_confirmation",
                "plan_item_id": session_context.get("plan_item_id"),
                "area_record_id": session_context.get("area_record_id"),
            },
        }
        return {
            "type": "action_proposal",
            "action": "submit_audit_evidence",
            "status": "pending",
            "title": "提交正式审核证据并生成多条款草稿",
            "data": {
                "project_id": project_id,
                "audit_session_id": session_id,
                "plan_item_id": session_context.get("plan_item_id"),
                "area_record_id": session_context.get("area_record_id"),
                "evidence": content,
                "confirm_endpoint": f"/api/audit-projects/{project_id}/sessions/{session_id}/evidence",
                "confirm_method": "POST",
                "confirm_payload": payload,
            },
        }

    async def _tool_propose_audit_draft_confirmation(
        self,
        args: dict,
        context: dict,
        db: AsyncSession,
    ) -> dict:
        project_id = self._normalize_uuid(context.get("project_id"))
        session_id = self._normalize_uuid(context.get("audit_session_id"))
        safe_only = bool(args.get("safe_only"))
        draft_ids = [
            value
            for value in (
                self._normalize_uuid(item) for item in (args.get("draft_ids") or [])
            )
            if value
        ]
        if not project_id or not session_id:
            return {"error": "草稿确认需要项目ID和审核会话ID"}
        if not safe_only and not draft_ids:
            return {"error": "请选择要确认的AI草稿，或启用仅确认安全项"}

        if draft_ids:
            rows = await db.execute(
                select(AiDraftRecord.id).where(
                    AiDraftRecord.id.in_(draft_ids),
                    AiDraftRecord.project_id == project_id,
                    AiDraftRecord.session_id == session_id,
                    AiDraftRecord.status == "draft",
                )
            )
            valid_ids = {str(value) for value in rows.scalars().all()}
            if valid_ids != set(draft_ids):
                return {"error": "包含不属于当前项目会话的草稿，无法确认"}

        payload = {
            "draft_ids": draft_ids,
            "action": "confirm",
            "safe_only": safe_only,
            "overrides": [],
        }
        return {
            "type": "action_proposal",
            "action": "confirm_audit_drafts",
            "status": "pending",
            "title": "确认AI草稿并写入正式区域记录",
            "data": {
                "project_id": project_id,
                "audit_session_id": session_id,
                "draft_count": len(draft_ids),
                "safe_only": safe_only,
                "confirm_endpoint": f"/api/audit-projects/{project_id}/sessions/{session_id}/drafts/confirm",
                "confirm_method": "POST",
                "confirm_payload": payload,
            },
        }

    async def _tool_apply_final_verdict(
        self,
        args: dict,
        context: dict,
        db: AsyncSession,
    ) -> dict:
        """Build a final-verdict write proposal. Does NOT write to the database -
        the frontend renders this as a confirmation card, and only calls the real
        write endpoint (PUT /api/records/{record_id}) after the inspector clicks '采纳'."""
        record_id = self._normalize_uuid(
            context.get("record_id") or args.get("record_id")
        )
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
