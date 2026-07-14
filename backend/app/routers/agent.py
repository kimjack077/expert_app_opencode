import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.agent_conversation import AgentConversation, AgentMessage
from app.services.agent_service import agent_service
from app.utils.security import get_current_user


router = APIRouter()


class ChatContext(BaseModel):
    record_id: Optional[str] = None
    current_item_id: Optional[str] = None
    enterprise_id: Optional[str] = None
    media_file_id: Optional[str] = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    context: Optional[ChatContext] = None
    conversation: Optional[List[ChatMessage]] = None
    conversation_id: Optional[str] = None


def make_response(data=None, code=200, message="success"):
    from datetime import datetime, timezone

    return {
        "code": code,
        "message": message,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


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
    context = request.context.model_dump() if request.context else {}

    conversation = await _load_or_create_conversation(
        request.conversation_id, context, current_user, db
    )

    # History: prefer what the client sent (it already has the freshest local
    # state); fall back to DB history when the client didn't send any - this
    # lets a client resume a conversation_id without replaying every message.
    if request.conversation:
        history = [msg.model_dump() for msg in request.conversation]
    else:
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

    user_message = AgentMessage(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    db.add(user_message)
    await db.commit()

    async def event_generator():
        assistant_text = ""
        tool_call_log = []
        action_proposals = []

        try:
            yield f"data: {json.dumps({'type': 'conversation', 'conversation_id': str(conversation.id)}, ensure_ascii=False)}\n\n"

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
                    action_proposals.append(event)

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        except Exception as e:
            error_event = {"type": "error", "content": str(e)}
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

        finally:
            assistant_message = AgentMessage(
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_text,
                tool_calls=tool_call_log or None,
                extra_data={"action_proposals": action_proposals} if action_proposals else None,
            )
            db.add(assistant_message)
            try:
                await db.commit()
            except Exception as persist_err:
                print(f"[Agent] Failed to persist assistant message: {persist_err}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/briefing/{enterprise_id}")
async def get_briefing(
    enterprise_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """检查前准备简报：企业概况 + 历史遗留问题 + 相关法规 + 重点关注清单"""
    briefing = await agent_service.generate_briefing(enterprise_id, db)
    if "error" in briefing:
        raise HTTPException(status_code=404, detail=briefing["error"])
    return make_response(data=briefing)


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
