from typing import AsyncIterator, Optional
import json

from app.agents.base import AgentState
from app.agents.registry import get_agent
from app.services.intent.classifier import classify_intent, AgentType
from app.core.redis import get_redis, SessionCache, HotQACache
from app.common.exceptions import AgentException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.database import Message


class Orchestrator:
    def __init__(self):
        self._session_cache: Optional[SessionCache] = None
        self._hotqa_cache: Optional[HotQACache] = None

    async def _get_session_cache(self) -> SessionCache:
        if self._session_cache is None:
            redis = await get_redis()
            self._session_cache = SessionCache(redis)
        return self._session_cache

    async def _get_hotqa_cache(self) -> HotQACache:
        if self._hotqa_cache is None:
            redis = await get_redis()
            self._hotqa_cache = HotQACache(redis)
        return self._hotqa_cache

    async def _load_messages_from_db(self, conversation_id: int, db: AsyncSession) -> list[dict]:
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()
        return [
            {
                "role": m.role,
                "content": m.content,
                "agent_type": m.agent_type,
            }
            for m in messages
        ]

    async def _get_conversation_messages(
        self,
        conversation_id: int,
        db: AsyncSession,
    ) -> list[dict]:
        session_cache = await self._get_session_cache()
        cached = await session_cache.get_messages(conversation_id)
        
        if cached is not None and len(cached) < 50:
            return cached

        messages = await self._load_messages_from_db(conversation_id, db)
        if messages:
            await session_cache.set_messages(conversation_id, messages)
        return messages

    async def dispatch(
        self,
        query: str,
        user_id: int,
        conversation_id: Optional[int] = None,
        agent_type: Optional[str] = None,
        context: Optional[dict] = None,
        db: Optional[AsyncSession] = None,
    ) -> AgentState:
        resolved_type = None
        if agent_type:
            try:
                resolved_type = AgentType(agent_type)
            except ValueError:
                pass
        
        if resolved_type is None:
            resolved_type = await classify_intent(query)

        agent = get_agent(resolved_type)
        if agent is None:
            raise AgentException(f"未找到Agent: {resolved_type}")

        messages = []
        if conversation_id and db:
            messages = await self._get_conversation_messages(conversation_id, db)

        state: AgentState = {
            "query": query,
            "conversation_id": conversation_id or 0,
            "user_id": user_id,
            "messages": messages,
            "context": context or {},
            "agent_type": resolved_type.value,
            "intermediate_results": [],
            "final_answer": "",
            "confidence": 0.0,
            "metadata": {},
            "error": None,
        }

        if resolved_type == AgentType.QA and not agent_type:
            hotqa_cache = await self._get_hotqa_cache()
            cached_answer = await hotqa_cache.get(query)
            if cached_answer:
                state["final_answer"] = cached_answer
                state["confidence"] = 1.0
                state["metadata"]["from_cache"] = True
                return state

        result = await agent.run(state)
        return result

    async def dispatch_stream(
        self,
        query: str,
        user_id: int,
        conversation_id: Optional[int] = None,
        agent_type: Optional[str] = None,
        context: Optional[dict] = None,
        db: Optional[AsyncSession] = None,
    ) -> AsyncIterator[str]:
        resolved_type = None
        if agent_type:
            try:
                resolved_type = AgentType(agent_type)
            except ValueError:
                pass
        
        if resolved_type is None:
            resolved_type = await classify_intent(query)

        agent = get_agent(resolved_type)
        if agent is None:
            raise AgentException(f"未找到Agent: {resolved_type}")

        messages = []
        if context and context.get("history_messages"):
            messages = context["history_messages"]
        elif conversation_id and db:
            messages = await self._get_conversation_messages(conversation_id, db)

        state: AgentState = {
            "query": query,
            "conversation_id": conversation_id or 0,
            "user_id": user_id,
            "messages": messages,
            "context": context or {},
            "agent_type": resolved_type.value,
            "intermediate_results": [],
            "final_answer": "",
            "confidence": 0.0,
            "metadata": {},
            "error": None,
        }

        full_answer = ""
        async for chunk in agent.stream(state):
            full_answer += chunk
            yield chunk

        confidence = state.get("confidence", 0)
        if confidence == 0:
            confidence = state.get("context", {}).get("confidence", 0)
        yield json.dumps({"confidence": confidence}, ensure_ascii=False)


_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
