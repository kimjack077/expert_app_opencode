import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.agent_service import agent_service


router = APIRouter()


class ChatContext(BaseModel):
    record_id: Optional[str] = None
    current_item_id: Optional[str] = None
    enterprise_id: Optional[str] = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    context: Optional[ChatContext] = None
    conversation: Optional[List[ChatMessage]] = None


@router.post("/chat")
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    async def event_generator():
        try:
            context = request.context.model_dump() if request.context else {}
            conversation = [msg.model_dump() for msg in request.conversation] if request.conversation else []
            
            async for event in agent_service.chat_stream(
                message=request.message,
                context=context,
                conversation=conversation,
                db=db,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                
        except Exception as e:
            error_event = {"type": "error", "content": str(e)}
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
