from typing import TypedDict, Optional, Any, AsyncIterator
from abc import ABC, abstractmethod

from app.services.llm.factory import LLMFactory
from app.core.redis import get_redis, SummaryCache


SUMMARY_PROMPT = """请将以下多轮对话历史压缩为一段简洁的摘要，保留关键信息和上下文要点：

{conversation}

摘要："""


class AgentState(TypedDict, total=False):
    query: str
    conversation_id: int
    user_id: int
    messages: list[dict]
    context: dict
    agent_type: str
    intermediate_results: list[dict]
    final_answer: str
    confidence: float
    metadata: dict
    error: Optional[str]


class BaseAgent(ABC):
    agent_type: str = ""
    agent_name: str = ""
    agent_description: str = ""
    max_context_messages: int = 10
    summary_threshold: int = 20

    @abstractmethod
    async def run(self, state: AgentState) -> AgentState:
        pass

    @abstractmethod
    async def stream(self, state: AgentState) -> AsyncIterator[str]:
        pass

    def build_system_prompt(self, state: AgentState) -> str:
        return f"你是{self.agent_name}。{self.agent_description}"

    async def summarize_messages(self, messages: list[dict]) -> str:
        if not messages:
            return ""
        conversation_text = "\n".join(
            [f"{m['role']}: {m['content']}" for m in messages]
        )
        summary = await LLMFactory.chat(
            messages=[{"role": "user", "content": SUMMARY_PROMPT.format(conversation=conversation_text)}],
            temperature=0.0,
        )
        return summary.strip()

    def format_messages(self, state: AgentState) -> list[dict]:
        messages = [{"role": "system", "content": self.build_system_prompt(state)}]
        
        history = state.get("messages", [])
        
        if len(history) > self.summary_threshold:
            recent_messages = history[-self.max_context_messages:]
            
            summary = state.get("context", {}).get("conversation_summary", "")
            if summary:
                messages.append({
                    "role": "system",
                    "content": f"以下是之前对话的摘要：\n{summary}"
                })
            
            messages.extend(recent_messages)
        else:
            if history:
                for msg in history[-self.max_context_messages:]:
                    messages.append(msg)
        
        messages.append({"role": "user", "content": state["query"]})
        return messages

    async def format_messages_async(self, state: AgentState) -> tuple[list[dict], Optional[str]]:
        messages = [{"role": "system", "content": self.build_system_prompt(state)}]
        
        history = state.get("messages", [])
        summary = None
        
        if len(history) > self.summary_threshold:
            summary_messages = history[:-self.max_context_messages]
            recent_messages = history[-self.max_context_messages:]
            
            conversation_id = state.get("conversation_id")
            cached_summary = None
            cached_count = 0
            
            if conversation_id:
                try:
                    redis = await get_redis()
                    summary_cache = SummaryCache(redis)
                    cached_summary, cached_count = await summary_cache.get(conversation_id)
                except Exception:
                    pass
            
            need_regenerate = (
                not cached_summary or
                len(summary_messages) - cached_count >= 5
            )
            
            if need_regenerate:
                summary = await self.summarize_messages(summary_messages)
                if summary and conversation_id:
                    try:
                        redis = await get_redis()
                        summary_cache = SummaryCache(redis)
                        await summary_cache.set(conversation_id, summary, len(summary_messages))
                    except Exception:
                        pass
            else:
                summary = cached_summary
            
            if summary:
                messages.append({
                    "role": "system",
                    "content": f"以下是之前对话的摘要：\n{summary}"
                })
            
            messages.extend(recent_messages)
        else:
            if history:
                for msg in history[-self.max_context_messages:]:
                    messages.append(msg)
        
        messages.append({"role": "user", "content": state["query"]})
        return messages, summary
