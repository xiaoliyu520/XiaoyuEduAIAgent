from typing import AsyncIterator, Optional
import json

from app.agents.base import AgentState
from app.agents.registry import get_agent
from app.services.intent.classifier import classify_intent, AgentType
from app.core.redis import get_redis, SessionCache, HotQACache
from app.common.exceptions import AgentException


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

    async def dispatch(
        self,
        query: str,
        user_id: int,
        conversation_id: Optional[int] = None,
        agent_type: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> AgentState:
        if agent_type:
            try:
                resolved_type = AgentType(agent_type)
            except ValueError:
                resolved_type = await classify_intent(query)
        else:
            resolved_type = await classify_intent(query)

        agent = get_agent(resolved_type)
        if agent is None:
            raise AgentException(f"未找到Agent: {resolved_type}")

        session_cache = await self._get_session_cache()
        messages = []
        if conversation_id:
            cached = await session_cache.get_messages(conversation_id)
            messages = cached

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

        if conversation_id:
            await session_cache.add_message(conversation_id, {
                "role": "user",
                "content": query,
            })
            await session_cache.add_message(conversation_id, {
                "role": "assistant",
                "content": result.get("final_answer", ""),
                "agent_type": resolved_type.value,
            })

        if resolved_type == AgentType.QA and result.get("confidence", 0) >= 0.8:
            hotqa_cache = await self._get_hotqa_cache()
            await hotqa_cache.set(query, result.get("final_answer", ""))

        return result

    async def dispatch_stream(
        self,
        query: str,
        user_id: int,
        conversation_id: Optional[int] = None,
        agent_type: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> AsyncIterator[str]:
        if agent_type:
            try:
                resolved_type = AgentType(agent_type)
            except ValueError:
                resolved_type = await classify_intent(query)
        else:
            resolved_type = await classify_intent(query)

        agent = get_agent(resolved_type)
        if agent is None:
            raise AgentException(f"未找到Agent: {resolved_type}")

        session_cache = await self._get_session_cache()
        messages = []
        if conversation_id:
            cached = await session_cache.get_messages(conversation_id)
            messages = cached

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

        if conversation_id:
            await session_cache.add_message(conversation_id, {
                "role": "user",
                "content": query,
            })
            await session_cache.add_message(conversation_id, {
                "role": "assistant",
                "content": full_answer,
                "agent_type": resolved_type.value,
            })


_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
