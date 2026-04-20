from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from app.core.database import get_db
from app.models.database import User, Conversation, Message, KnowledgeBase, KnowledgeGap
from app.models.schemas import ChatRequest, ResponseBase, ConversationResponse, ChatMessage
from app.api.deps import get_current_user
from app.orchestrator.orchestrator import get_orchestrator
from app.core.redis import get_redis, SessionCache

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
    elif not conversation.title or conversation.title == "新对话":
        conversation.title = data.message[:50]
        await db.commit()

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

    collection_names = []
    if data.kb_ids:
        kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id.in_(data.kb_ids)))
        kbs = kb_result.scalars().all()
        collection_names = [kb.collection_name for kb in kbs]
        context["collection_names"] = collection_names

    result = await orchestrator.dispatch(
        query=data.message,
        user_id=current_user.id,
        conversation_id=conversation.id,
        agent_type=data.agent_type,
        context=context,
        db=db,
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

    if result.get("confidence", 0) < 0.5:
        kb_id = data.kb_ids[0] if data.kb_ids else None
        existing_gap = None
        if kb_id:
            existing_gap = await db.execute(
                select(KnowledgeGap).where(
                    KnowledgeGap.question == data.message,
                    KnowledgeGap.kb_id == kb_id,
                    KnowledgeGap.status == "open",
                )
            )
            existing_gap = existing_gap.scalar_one_or_none()
        
        if not existing_gap:
            ai_answer = result.get("answer", "")
            gap = KnowledgeGap(
                question=data.message,
                kb_id=kb_id,
                source_conversation_id=conversation.id,
                status="open",
                answer=ai_answer,
            )
            db.add(gap)

    await db.commit()

    redis = await get_redis()
    session_cache = SessionCache(redis)
    await session_cache.add_message(conversation.id, {"role": "user", "content": data.message})
    await session_cache.add_message(conversation.id, {"role": "assistant", "content": result.get("final_answer", "")})

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
    if not data.kb_ids or len(data.kb_ids) == 0:
        kb_result = await db.execute(select(KnowledgeBase))
        all_kbs = kb_result.scalars().all()
        if not all_kbs:
            async def error_generator():
                yield f"data: {json.dumps({'error': '系统中没有可用的知识库，请联系管理员创建知识库'}, ensure_ascii=False)}\n\n"
            return StreamingResponse(error_generator(), media_type="text/event-stream")
        else:
            async def error_generator():
                yield f"data: {json.dumps({'error': '请选择至少一个知识库'}, ensure_ascii=False)}\n\n"
            return StreamingResponse(error_generator(), media_type="text/event-stream")

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
    elif not conversation.title or conversation.title == "新对话":
        conversation.title = data.message[:50]
        await db.commit()

    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=data.message,
    )
    db.add(user_msg)
    await db.commit()

    context = data.context or {}

    collection_names = []
    kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id.in_(data.kb_ids)))
    kbs = kb_result.scalars().all()
    collection_names = [kb.collection_name for kb in kbs]
    context["collection_names"] = collection_names

    history_messages = await orchestrator._get_conversation_messages(conversation.id, db)
    context["history_messages"] = history_messages

    async def event_generator():
        full_answer = ""
        confidence = 0.0
        query_type = "clear"
        try:
            async for chunk in orchestrator.dispatch_stream(
                query=data.message,
                user_id=current_user.id,
                conversation_id=conversation.id,
                agent_type=data.agent_type,
                context=context,
                db=None,
            ):
                if chunk.startswith("{") and "confidence" in chunk:
                    try:
                        parsed = json.loads(chunk)
                        confidence = parsed.get("confidence", 0)
                        query_type = parsed.get("query_type", "clear")
                        continue
                    except:
                        pass
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

        if query_type != "chitchat" and confidence < 0.5:
            kb_id = data.kb_ids[0] if data.kb_ids else None
            existing_gap = None
            if kb_id:
                existing_gap = await db.execute(
                    select(KnowledgeGap).where(
                        KnowledgeGap.question == data.message,
                        KnowledgeGap.kb_id == kb_id,
                        KnowledgeGap.status == "open",
                    )
                )
                existing_gap = existing_gap.scalar_one_or_none()
            
            if not existing_gap:
                ai_answer = full_answer
                warning_idx = ai_answer.find("⚠️ 以上回答仅供参考")
                if warning_idx > 0:
                    ai_answer = ai_answer[:warning_idx].strip()
                gap = KnowledgeGap(
                    question=data.message,
                    kb_id=kb_id,
                    source_conversation_id=conversation.id,
                    status="open",
                    answer=ai_answer,
                )
                db.add(gap)

        await db.commit()

        redis = await get_redis()
        session_cache = SessionCache(redis)
        await session_cache.add_message(conversation.id, {"role": "user", "content": data.message})
        await session_cache.add_message(conversation.id, {"role": "assistant", "content": full_answer})

        done_data = json.dumps({
            "done": True,
            "conversation_id": conversation.id,
            "confidence": confidence,
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
    redis = await get_redis()
    session_cache = SessionCache(redis)
    for conv in conversations:
        msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at)
        )
        messages = msg_result.scalars().all()
        msg_list = [
            {
                "role": m.role,
                "content": m.content,
                "agent_type": m.agent_type,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ]
        items.append({
            "id": conv.id,
            "agent_type": conv.agent_type,
            "title": conv.title,
            "created_at": conv.created_at.isoformat(),
            "messages": msg_list,
        })
        await session_cache.set_messages(conv.id, msg_list)
    return ResponseBase(data=items)


@router.post("/conversations", response_model=ResponseBase)
async def create_conversation(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conversation = Conversation(
        user_id=current_user.id,
        agent_type="qa",
        title="新对话",
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return ResponseBase(data={
        "id": conversation.id,
        "agent_type": conversation.agent_type,
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat(),
        "messages": [],
    })


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

    redis = await get_redis()
    session_cache = SessionCache(redis)
    await session_cache.clear(conversation_id)

    return ResponseBase(message="对话已删除")
