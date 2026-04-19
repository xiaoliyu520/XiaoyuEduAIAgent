from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from app.core.database import get_db
from app.models.database import User, Conversation, Message
from app.models.schemas import ChatRequest, ResponseBase, ConversationResponse, ChatMessage
from app.api.deps import get_current_user
from app.orchestrator.orchestrator import get_orchestrator

router = APIRouter(prefix="/chat", tags=["对话"])


@router.post("")
async def chat(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    orchestrator = get_orchestrator()

    conversation = None
    if data.conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == data.conversation_id,
                Conversation.user_id == current_user.id,
            )
        )
        conversation = result.scalar_one_or_none()

    if conversation is None:
        conversation = Conversation(
            user_id=current_user.id,
            agent_type=data.agent_type or "qa",
            title=data.message[:50],
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=data.message,
    )
    db.add(user_msg)
    await db.commit()

    context = data.context or {}
    if data.agent_type == "code" and context.get("code"):
        pass
    if data.agent_type == "interview" and context.get("stage"):
        pass

    result = await orchestrator.dispatch(
        query=data.message,
        user_id=current_user.id,
        conversation_id=conversation.id,
        agent_type=data.agent_type,
        context=context,
    )

    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=result.get("final_answer", ""),
        agent_type=result.get("agent_type", ""),
        metadata_json=json.dumps({
            "confidence": result.get("confidence", 0),
            "metadata": result.get("metadata", {}),
        }, ensure_ascii=False),
    )
    db.add(assistant_msg)
    await db.commit()

    return ResponseBase(data={
        "conversation_id": conversation.id,
        "answer": result.get("final_answer", ""),
        "agent_type": result.get("agent_type", ""),
        "confidence": result.get("confidence", 0),
    })


@router.post("/stream")
async def chat_stream(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    orchestrator = get_orchestrator()

    conversation = None
    if data.conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == data.conversation_id,
                Conversation.user_id == current_user.id,
            )
        )
        conversation = result.scalar_one_or_none()

    if conversation is None:
        conversation = Conversation(
            user_id=current_user.id,
            agent_type=data.agent_type or "qa",
            title=data.message[:50],
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=data.message,
    )
    db.add(user_msg)
    await db.commit()

    context = data.context or {}

    async def event_generator():
        full_answer = ""
        try:
            async for chunk in orchestrator.dispatch_stream(
                query=data.message,
                user_id=current_user.id,
                conversation_id=conversation.id,
                agent_type=data.agent_type,
                context=context,
            ):
                full_answer += chunk
                event_data = json.dumps({"content": chunk}, ensure_ascii=False)
                yield f"data: {event_data}\n\n"
        except Exception as e:
            error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"data: {error_data}\n\n"

        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=full_answer,
            agent_type=data.agent_type or "",
        )
        db.add(assistant_msg)
        await db.commit()

        done_data = json.dumps({
            "done": True,
            "conversation_id": conversation.id,
        }, ensure_ascii=False)
        yield f"data: {done_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations", response_model=ResponseBase)
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    conversations = result.scalars().all()
    items = []
    for conv in conversations:
        msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at)
        )
        messages = msg_result.scalars().all()
        items.append({
            "id": conv.id,
            "agent_type": conv.agent_type,
            "title": conv.title,
            "created_at": conv.created_at.isoformat(),
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "agent_type": m.agent_type,
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
            ],
        })
    return ResponseBase(data=items)


@router.delete("/conversations/{conversation_id}", response_model=ResponseBase)
async def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise ValueError("对话不存在")
    msg_result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id)
    )
    for msg in msg_result.scalars().all():
        await db.delete(msg)
    await db.delete(conversation)
    await db.commit()
    return ResponseBase(message="对话已删除")
