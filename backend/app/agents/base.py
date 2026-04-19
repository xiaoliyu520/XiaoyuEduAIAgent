from typing import TypedDict, Optional, Any, AsyncIterator
from abc import ABC, abstractmethod


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

    @abstractmethod
    async def run(self, state: AgentState) -> AgentState:
        pass

    @abstractmethod
    async def stream(self, state: AgentState) -> AsyncIterator[str]:
        pass

    def build_system_prompt(self, state: AgentState) -> str:
        return f"你是{self.agent_name}。{self.agent_description}"

    def format_messages(self, state: AgentState) -> list[dict]:
        messages = [{"role": "system", "content": self.build_system_prompt(state)}]
        if state.get("messages"):
            for msg in state["messages"][-10:]:
                messages.append(msg)
        messages.append({"role": "user", "content": state["query"]})
        return messages
