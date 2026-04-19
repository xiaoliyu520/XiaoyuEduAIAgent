from langchain_community.chat_models import ChatTongyi
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from typing import AsyncIterator, Optional
import os

from app.core.config import get_settings
from app.common.exceptions import LLMException

settings = get_settings()


class LLMFactory:
    _instances: dict[str, BaseChatModel] = {}

    @classmethod
    def get_chat_model(cls, model_name: Optional[str] = None, temperature: float = 0.7) -> BaseChatModel:
        name = model_name or settings.LLM_MODEL_NAME
        key = f"{name}_{temperature}"
        if key not in cls._instances:
            os.environ["DASHSCOPE_API_KEY"] = settings.DASHSCOPE_API_KEY
            cls._instances[key] = ChatTongyi(
                model=name,
                temperature=temperature,
                streaming=True,
            )
        return cls._instances[key]

    @classmethod
    async def chat(
        cls,
        messages: list[dict],
        model_name: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        try:
            llm = cls.get_chat_model(model_name, temperature)
            lc_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    lc_messages.append(SystemMessage(content=msg["content"]))
                elif msg["role"] == "user":
                    lc_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    lc_messages.append(AIMessage(content=msg["content"]))
            response = await llm.ainvoke(lc_messages)
            return response.content
        except Exception as e:
            raise LLMException(f"LLM调用失败: {str(e)}")

    @classmethod
    async def chat_stream(
        cls,
        messages: list[dict],
        model_name: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        try:
            llm = cls.get_chat_model(model_name, temperature)
            lc_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    lc_messages.append(SystemMessage(content=msg["content"]))
                elif msg["role"] == "user":
                    lc_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    lc_messages.append(AIMessage(content=msg["content"]))
            async for chunk in llm.astream(lc_messages):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            raise LLMException(f"LLM流式调用失败: {str(e)}")

    @classmethod
    async def chat_with_tools(
        cls,
        messages: list[dict],
        tools: list,
        model_name: Optional[str] = None,
        temperature: float = 0.0,
    ):
        try:
            llm = cls.get_chat_model(model_name, temperature)
            llm_with_tools = llm.bind_tools(tools)
            lc_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    lc_messages.append(SystemMessage(content=msg["content"]))
                elif msg["role"] == "user":
                    lc_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    lc_messages.append(AIMessage(content=msg["content"]))
            response = await llm_with_tools.ainvoke(lc_messages)
            return response
        except Exception as e:
            raise LLMException(f"LLM工具调用失败: {str(e)}")
