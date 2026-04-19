from app.agents.qa.agent import QAAgent
from app.agents.resume.agent import ResumeAgent
from app.agents.interview.agent import InterviewAgent
from app.agents.code.agent import CodeAgent
from app.agents.base import BaseAgent, AgentState
from app.services.intent.classifier import AgentType

_agent_registry: dict[AgentType, BaseAgent] = {}


def get_agent_registry() -> dict[AgentType, BaseAgent]:
    global _agent_registry
    if not _agent_registry:
        _agent_registry = {
            AgentType.QA: QAAgent(),
            AgentType.RESUME: ResumeAgent(),
            AgentType.INTERVIEW: InterviewAgent(),
            AgentType.CODE: CodeAgent(),
        }
    return _agent_registry


def get_agent(agent_type: AgentType) -> BaseAgent:
    registry = get_agent_registry()
    return registry.get(agent_type)
