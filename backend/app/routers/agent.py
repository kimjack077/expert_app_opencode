import asyncio
import json
import logging
from typing import Optional, List
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.database import AsyncSessionLocal, get_db
from app.models.user import User
from app.models.agent_conversation import AgentConversation, AgentMessage
from app.models.record import InspectionRecord, InspectionRecordItem
from app.models.task import InspectionTask
from app.services.agent_actions import execute_action, registered_actions
from app.utils.roles import ADMIN_ROLES
from app.services.agent_service import agent_service
from app.services.formal_audit_sync_service import can_access_linked_task
from app.services.project_access_service import ensure_project_access
from app.utils.security import get_current_user


logger = logging.getLogger(__name__)

router = APIRouter()


class ChatContext(BaseModel):
    page: Optional[str] = None
    record_id: Optional[str] = None
    task_id: Optional[str] = None
    current_item_id: Optional[str] = None
    enterprise_id: Optional[str] = None
    media_file_id: Optional[str] = None
    project_id: Optional[str] = None
    audit_session_id: Optional[str] = None
    plan_item_id: Optional[str] = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    context: Optional[ChatContext] = None
    conversation: Optional[List[ChatMessage]] = None
    conversation_id: Optional[str] = None


from app.utils.response import make_response  # noqa: E402  统一响应封装


async def _persist_assistant_message(
    message_id: UUID,
    conversation_id: UUID,
    content: str,
    tool_calls: list,
    proposals: list,
) -> None:
    """幂等 upsert 助手消息（含动作提案）。

    永远使用独立会话：调用点位于 SSE 流中/收尾，请求级 session 可能已被
    中间件取消而不可用。可重复调用——流中每产生一条提案就调一次。
    """
    async with AsyncSessionLocal() as sdb:
        existing = await sdb.get(AgentMessage, message_id)
        extra = {"action_proposals": proposals} if proposals else None
        if existing:
            existing.content = content
            existing.tool_calls = tool_calls or None
            existing.extra_data = extra
        else:
            sdb.add(AgentMessage(
                id=message_id,
                conversation_id=conversation_id,
                role="assistant",
                content=content,
                tool_calls=tool_calls or None,
                extra_data=extra,
            ))
        await sdb.commit()


async def _authorize_chat_context(
    context: dict, current_user: User, db: AsyncSession
) -> None:
    """在开聊之前统一校验上下文中的资源归属。

    Agent 工具直接拿 context 里的 ID 查库。如果不在这里校验，
    调用方只要伪造 record_id / current_item_id，就能让 Agent
    读出他人的检查记录（越权读）。在单一入口校验比逐个工具补更可靠。
    """
    if context.get("project_id"):
        try:
            project_id = UUID(context["project_id"])
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="项目 ID 格式不正确") from exc
        await ensure_project_access(db, project_id, current_user)

    if current_user.role in ADMIN_ROLES:
        return

    # 任务模式（H5 任务检查页）上下文带的是 task_id 而非 record_id，
    # 按任务归属校验：分配人本人，或经正式审核计划项关联可访问。
    task_id = context.get("task_id")
    if task_id:
        try:
            task_uuid = UUID(str(task_id))
        except ValueError:
            raise HTTPException(status_code=422, detail="检查任务 ID 格式不正确")
        task = await db.get(InspectionTask, task_uuid)
        if not task or task.is_deleted:
            raise HTTPException(status_code=404, detail="检查任务不存在")
        if str(task.assigned_to) != str(current_user.id) and not await can_access_linked_task(
            db, task, current_user
        ):
            raise HTTPException(status_code=403, detail="无权访问该检查任务")

    record_id = context.get("record_id")
    item_id = context.get("current_item_id")

    # current_item_id 的归属由其所属记录决定
    if item_id and not record_id:
        try:
            item = await db.get(InspectionRecordItem, UUID(str(item_id)))
        except ValueError:
            raise HTTPException(status_code=422, detail="检查项 ID 格式不正确")
        if item and item.record_id:
            record_id = str(item.record_id)

    if not record_id:
        return

    try:
        record_uuid = UUID(str(record_id))
    except ValueError:
        raise HTTPException(status_code=422, detail="检查记录 ID 格式不正确")

    record = (
        await db.execute(
            select(InspectionRecord).where(
                InspectionRecord.id == record_uuid,
                InspectionRecord.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="检查记录不存在")
    if str(record.inspector_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="无权访问该检查记录")


async def _load_or_create_conversation(
    conversation_id: Optional[str],
    context: dict,
    current_user: User,
    db: AsyncSession,
) -> AgentConversation:
    if conversation_id:
        conv = await db.get(AgentConversation, conversation_id)
        if conv and str(conv.user_id) == str(current_user.id):
            return conv

    conv = AgentConversation(user_id=current_user.id, context=context)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


@router.post("/chat")
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # BUG-21：空消息前置拦截——原实现会把空串直接发给主模型（400 user content required），
    # 触发一次无谓的降级切换与日志噪声。
    if not (request.message or "").strip():
        raise HTTPException(status_code=422, detail="消息内容不能为空")

    context = request.context.model_dump() if request.context else {}
    await _authorize_chat_context(context, current_user, db)

    conversation = await _load_or_create_conversation(
        request.conversation_id, context, current_user, db
    )

    # 会话历史以服务端持久化的为准。
    # 原先「前端传入优先」意味着客户端可以任意改写模型看到的历史
    # （包括伪造 assistant 说过的话来诱导后续判定），既不安全，
    # 也让「换设备继续对话」的记忆不可靠。
    # 仅当该会话在服务端尚无历史时，才接受客户端传入作为一次性迁移兜底。
    result = await db.execute(
        select(AgentMessage)
        .where(AgentMessage.conversation_id == conversation.id)
        .order_by(AgentMessage.created_at)
    )
    history = [
        {"role": m.role, "content": m.content or ""}
        for m in result.scalars().all()
        if m.role in ("user", "assistant")
    ]
    if not history and request.conversation:
        history = [msg.model_dump() for msg in request.conversation]

    user_message = AgentMessage(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    db.add(user_message)
    await db.commit()

    # 预先生成助手消息 ID：动作提案由服务端持久化在这条消息上，
    # 客户端确认时只回传 (message_id, action_index)，不回传动作内容本身。
    assistant_message_id = uuid4()

    async def event_generator():
        assistant_text = ""
        tool_call_log = []
        action_proposals = []

        try:
            yield f"data: {json.dumps({'type': 'conversation', 'conversation_id': str(conversation.id), 'message_id': str(assistant_message_id)}, ensure_ascii=False)}\n\n"

            async for event in agent_service.chat_stream(
                message=request.message,
                context=context,
                conversation=history,
                db=db,
                user_id=str(current_user.id),
            ):
                if event.get("type") == "content":
                    assistant_text += event.get("content", "")
                elif event.get("type") == "tool_call":
                    tool_call_log.append({"tool": event.get("tool"), "status": "calling"})
                elif event.get("type") == "action_proposal":
                    # 标注序号，供前端确认时引用服务端存储的这一条
                    event = {**event, "action_index": len(action_proposals),
                             "message_id": str(assistant_message_id)}
                    action_proposals.append(event)
                    # 关键：**流进行中立即落库**，不能留到 finally。
                    # SSE 收尾时 BaseHTTPMiddleware 会取消内部任务，届时
                    # finally 里的任何 await 都会被取消，提案将永远写不进去，
                    # 导致 /actions/confirm 返回 404（曾经的真实故障）。
                    await _persist_assistant_message(
                        assistant_message_id, conversation.id,
                        assistant_text, tool_call_log, action_proposals,
                    )

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        except Exception as e:
            print(f"[Agent] Chat request failed: {type(e).__name__}: {e}")
            error_event = {
                "type": "error",
                "content": "AI 助手暂时无法完成这次请求，请稍后重试。",
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

        finally:
            # 收尾补写完整正文/工具记录。用 shield 抵御任务取消；
            # 即便这里失败，动作提案在流中已落库，确认链路不受影响。
            try:
                await asyncio.shield(_persist_assistant_message(
                    assistant_message_id, conversation.id,
                    assistant_text, tool_call_log, action_proposals,
                ))
            except Exception as persist_err:
                print(f"[Agent] Failed to finalize assistant message: {persist_err}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class ActionConfirmRequest(BaseModel):
    message_id: str
    action_index: int = 0
    # 允许审核员在确认前修改建议内容；只有白名单字段会被采纳
    overrides: Optional[dict] = None


# 审核员可覆写的字段白名单。不在名单内的键一律丢弃，
# 避免通过 overrides 篡改 record_id / item_id 等关键定位字段。
_OVERRIDABLE_FIELDS = {
    "result",
    "verdict",
    "problem_description",
    "rectification_suggestion",
    "comment",
}


@router.post("/actions/confirm")
async def confirm_action(
    request: ActionConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """执行一条 Agent 动作提案。

    安全要点：执行内容取自**服务端持久化**的提案，客户端只能指定
    「执行哪一条」，不能指定「执行什么」。模型无法决定调用哪个接口，
    也无法构造请求体——这两件事都由服务端动作注册表控制。
    """
    try:
        message_uuid = UUID(request.message_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="message_id 不合法")

    message = (
        await db.execute(
            select(AgentMessage)
            .join(AgentConversation, AgentMessage.conversation_id == AgentConversation.id)
            .where(
                AgentMessage.id == message_uuid,
                AgentConversation.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="对话消息不存在")

    extra = dict(message.extra_data or {})
    proposals = list(extra.get("action_proposals") or [])
    if not 0 <= request.action_index < len(proposals):
        raise HTTPException(status_code=404, detail="动作提案不存在")

    proposal = dict(proposals[request.action_index])
    if proposal.get("status") == "applied":
        # 幂等：重复确认直接返回上次结果，不重复写库
        return make_response(
            data=proposal.get("result"), message="该操作已执行过"
        )

    data = dict(proposal.get("data") or {})
    for key, value in (request.overrides or {}).items():
        if key in _OVERRIDABLE_FIELDS:
            data[key] = value

    result = await execute_action(db, current_user, proposal.get("action"), data)

    proposal["status"] = "applied"
    proposal["result"] = result
    proposals[request.action_index] = proposal
    extra["action_proposals"] = proposals
    message.extra_data = extra
    flag_modified(message, "extra_data")
    await db.commit()

    return make_response(data=result, message="操作已执行")


@router.get("/actions/registry")
async def get_action_registry(current_user: User = Depends(get_current_user)):
    """列出服务端支持的动作，便于前端在渲染卡片时判断是否可一键执行。"""
    return make_response(data={"actions": registered_actions()})


@router.get("/notifications")
async def list_notifications(
    status: str = "unread",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """当前审核员的主动提醒（#6）。包含定向给本人的和面向管理角色的广播。"""
    from app.models.agent_runtime import AgentNotification

    conds = [
        or_(
            AgentNotification.user_id == current_user.id,
            AgentNotification.user_id.is_(None),  # 广播（如企业复审到期）
        )
    ]
    if status and status != "all":
        conds.append(AgentNotification.status == status)
    rows = (await db.execute(
        select(AgentNotification).where(*conds)
        .order_by(AgentNotification.created_at.desc()).limit(100)
    )).scalars().all()
    return make_response(data={
        "items": [
            {
                "id": str(n.id), "kind": n.kind, "severity": n.severity,
                "title": n.title, "body": n.body, "status": n.status,
                "enterprise_id": str(n.enterprise_id) if n.enterprise_id else None,
                "project_id": str(n.project_id) if n.project_id else None,
                "payload": n.payload, "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in rows
        ],
    })


class NotificationUpdate(BaseModel):
    status: str  # read / dismissed


@router.put("/notifications/{notification_id}")
async def update_notification(
    notification_id: str,
    body: NotificationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.agent_runtime import AgentNotification

    if body.status not in ("read", "dismissed", "unread"):
        raise HTTPException(status_code=400, detail="非法状态")
    try:
        nid = UUID(notification_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="notification_id 不合法")
    n = await db.get(AgentNotification, nid)
    if not n:
        raise HTTPException(status_code=404, detail="通知不存在")
    # 只能操作发给自己的或广播的
    if n.user_id is not None and str(n.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="无权操作该通知")
    n.status = body.status
    await db.commit()
    return make_response(message="已更新")


@router.get("/feedback/stats")
async def feedback_stats(
    project_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 草稿采纳/修改/拒绝率（#1）。按体系/条款/prompt 版本聚合。"""
    from app.services.agent_feedback_service import agent_feedback_service

    if current_user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="仅管理角色可查看反馈统计")
    pid = None
    if project_id:
        try:
            pid = UUID(project_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="project_id 不合法")
    return make_response(data=await agent_feedback_service.stats(db, pid))


class PlanRequest(BaseModel):
    goal: str
    context: Optional[ChatContext] = None


@router.post("/plan")
async def run_planner(
    request: PlanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """目标驱动规划器：把一个目标自主拆解为多步只读工具调用并汇总（SSE 流式）。

    与 /chat 的区别：/chat 是被动的多轮工具循环（用户问一句答一句），
    /plan 是主动的"给目标 → 自己规划 → 执行 → 汇总"，用于"准备明天的审核"这类复合任务。
    工具全部只读，不产生未确认写入。
    """
    from app.agents.planner import run_plan

    context = request.context.model_dump() if request.context else {}
    await _authorize_chat_context(context, current_user, db)

    async def event_generator():
        try:
            async for event in run_plan(
                goal=request.goal, context=context, db=db, user=current_user
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:
            print(f"[Planner] failed: {type(exc).__name__}: {exc}")
            yield f"data: {json.dumps({'type': 'error', 'content': '规划服务暂时不可用'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/models")
async def get_models(
    current_user: User = Depends(get_current_user),
):
    return make_response(
        data={
            "models": agent_service.get_available_models(),
            "default_model": agent_service.model,
            "vision_model": agent_service.vision_model,
        }
    )


@router.get("/briefing/{enterprise_id}")
async def get_briefing(
    enterprise_id: str,
    model: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """检查前准备简报：企业概况 + 历史遗留问题 + 相关法规 + 重点关注清单"""
    briefing = await agent_service.generate_briefing(
        enterprise_id, db, model_id=model, user_id=str(current_user.id)
    )
    if "error" in briefing:
        raise HTTPException(
            status_code=briefing.get("status_code", 404),
            detail=briefing["error"],
        )
    return make_response(data=briefing)


@router.get("/briefing/{enterprise_id}/stream")
async def stream_briefing(
    enterprise_id: str,
    model: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    async def event_generator():
        async for event in agent_service.generate_briefing_stream(
            enterprise_id,
            db,
            model_id=model,
            user_id=str(current_user.id),
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations")
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AgentConversation)
        .where(AgentConversation.user_id == current_user.id)
        .order_by(AgentConversation.updated_at.desc())
        .limit(50)
    )
    conversations = result.scalars().all()
    return make_response(
        data=[
            {
                "id": str(c.id),
                "title": c.title,
                "context": c.context,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in conversations
        ]
    )


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = await db.get(AgentConversation, conversation_id)
    if not conv or str(conv.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await db.execute(
        select(AgentMessage)
        .where(AgentMessage.conversation_id == conv.id)
        .order_by(AgentMessage.created_at)
    )
    messages = result.scalars().all()

    return make_response(
        data={
            "id": str(conv.id),
            "title": conv.title,
            "context": conv.context,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "tool_calls": m.tool_calls,
                    "extra_data": m.extra_data,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in messages
            ],
        }
    )
