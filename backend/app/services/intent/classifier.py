import os
from typing import Optional
from enum import Enum
from app.core.config import get_settings
from app.common.exceptions import IntentClassificationException
from app.services.llm.factory import LLMFactory

settings = get_settings()


class AgentType(str, Enum):
    QA = "qa"
    RESUME = "resume"
    INTERVIEW = "interview"
    CODE = "code"


INTENT_LABEL_NAMES_ZH = {
    AgentType.QA: "智能问答",
    AgentType.RESUME: "简历审查",
    AgentType.INTERVIEW: "模拟面试",
    AgentType.CODE: "代码检查",
}

INTENT_PROMPT = """你是一个意图分类器，请根据用户的输入判断其意图属于以下哪一类：

1. qa - 智能问答：用户询问课程知识、技术概念、学习资料等问题
2. resume - 简历审查：用户上传简历或请求简历审查、优化建议
3. interview - 模拟面试：用户请求模拟面试、面试练习
4. code - 代码检查：用户提交代码请求检查、调试、优化

用户输入：{query}

请只输出意图类别（qa/resume/interview/code），不要输出其他内容。"""


async def classify_intent(query: str) -> AgentType:
    try:
        result = await LLMFactory.chat(
            messages=[
                {"role": "system", "content": "你是一个意图分类器，只输出类别标签。"},
                {"role": "user", "content": INTENT_PROMPT.format(query=query)},
            ],
            temperature=0.0,
        )
        result = result.strip().lower()
        for agent_type in AgentType:
            if agent_type.value in result:
                return agent_type
        return AgentType.QA
    except Exception as e:
        raise IntentClassificationException(f"意图分类失败: {str(e)}")
