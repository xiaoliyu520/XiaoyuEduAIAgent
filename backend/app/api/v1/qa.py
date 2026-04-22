from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import json
import logging

logger = logging.getLogger(__name__)

from app.core.database import get_db, AsyncSessionLocal
from app.core.config import get_settings
from app.models.database import User, Conversation, Message, KnowledgeBase, KnowledgeGap
from app.models.schemas import ResponseBase, QAChatRequest
from app.api.deps import get_current_user
from app.agents.qa.agent import QAAgent
from app.core.redis import get_redis, SessionCache

router = APIRouter(prefix="/qa", tags=["智能问答"])


@router.post("/chat")
async def qa_chat(
    data: QAChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
            agent_type="qa",
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

    collection_names = []
    if data.kb_ids:
        kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id.in_(data.kb_ids)))
        kbs = kb_result.scalars().all()
        collection_names = [kb.collection_name for kb in kbs]

    agent = QAAgent()
    agent.collection_name = collection_names[0] if collection_names else "default"
    
    state = {
        "query": data.message,
        "context": {"collection_names": collection_names},
        "messages": [],
        "conversation_id": conversation.id,
        "user_id": current_user.id,
        "agent_type": "qa",
        "intermediate_results": [],
        "final_answer": "",
        "confidence": 0.0,
        "metadata": {},
        "error": None,
    }
    result = await agent.run(state)

    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=result.get("final_answer", ""),
        agent_type="qa",
        metadata_json=json.dumps({
            "confidence": result.get("confidence", 0),
            "metadata": result.get("metadata", {}),
        }, ensure_ascii=False),
    )
    db.add(assistant_msg)

    confidence = result.get("confidence", 0)
    query_type = result.get("context", {}).get("query_type", "clear")
    if query_type != "chitchat" and confidence < get_settings().RELEVANCE_THRESHOLD:
        kb_id = data.kb_ids[0] if data.kb_ids else None
        ai_answer = result.get("final_answer", "")
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

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        logger.info(f"KnowledgeGap already exists for question: {data.message[:50]}")

    redis = await get_redis()
    session_cache = SessionCache(redis)
    await session_cache.add_message(conversation.id, {"role": "user", "content": data.message})
    await session_cache.add_message(conversation.id, {"role": "assistant", "content": result.get("final_answer", "")})

    return ResponseBase(data={
        "conversation_id": conversation.id,
        "answer": result.get("final_answer", ""),
        "confidence": confidence,
    })


@router.post("/chat/stream")
async def qa_chat_stream(
    data: QAChatRequest,
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
            agent_type="qa",
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

    collection_names = []
    kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id.in_(data.kb_ids)))
    kbs = kb_result.scalars().all()
    collection_names = [kb.collection_name for kb in kbs]

    agent = QAAgent()
    agent.collection_name = collection_names[0] if collection_names else "default"

    async def event_generator():
        logger.info(f"event_generator 开始执行, query: {data.message[:30]}...")
        full_answer = ""
        confidence = 0.0
        query_type = "clear"
        stream_error = None
        
        state = {
            "query": data.message,
            "context": {"collection_names": collection_names},
            "messages": [],
            "conversation_id": conversation.id,
            "user_id": current_user.id,
            "agent_type": "qa",
            "intermediate_results": [],
            "final_answer": "",
            "confidence": 0.0,
            "metadata": {},
            "error": None,
        }
        
        try:
            logger.info(f"开始调用 agent.stream, collection_names: {collection_names}")
            async for chunk in agent.stream(state):
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
            logger.info(f"agent.stream 执行完成, full_answer 长度: {len(full_answer)}")
        except Exception as e:
            stream_error = str(e)
            logger.error(f"Agent stream error: {stream_error}", exc_info=True)
            error_data = json.dumps({"error": stream_error}, ensure_ascii=False)
            yield f"data: {error_data}\n\n"
            return

        async with AsyncSessionLocal() as stream_db:
            try:
                assistant_msg = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=full_answer,
                    agent_type="qa",
                )
                stream_db.add(assistant_msg)

                if query_type != "chitchat" and confidence < get_settings().RELEVANCE_THRESHOLD:
                    kb_id = data.kb_ids[0] if data.kb_ids else None
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
                    stream_db.add(gap)

                await stream_db.commit()
            except IntegrityError:
                await stream_db.rollback()
                logger.info(f"KnowledgeGap already exists for question: {data.message[:50]}")
            except Exception as e:
                await stream_db.rollback()
                logger.error(f"Database error: {e}", exc_info=True)

        try:
            redis = await get_redis()
            session_cache = SessionCache(redis)
            await session_cache.add_message(conversation.id, {"role": "user", "content": data.message})
            await session_cache.add_message(conversation.id, {"role": "assistant", "content": full_answer})
        except Exception as e:
            logger.error(f"Redis cache error: {e}", exc_info=True)

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
