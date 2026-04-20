from typing import AsyncIterator
import re
from langgraph.graph import StateGraph, END

from app.agents.base import BaseAgent, AgentState
from app.services.llm.factory import LLMFactory
from app.services.reranker.service import rerank_with_metadata
from app.mcp.milvus.client import search as milvus_search, hybrid_search as milvus_hybrid_search
from app.mcp.milvus.bm25 import get_bm25_index
from app.services.llm.factory import LLMFactory as LLM
import json
import logging

logger = logging.getLogger(__name__)


QA_SYSTEM_PROMPT = """你是一个专业的教育领域智能问答助手。你的职责是基于知识库内容，准确、专业地回答学员的问题。

回答要求：
1. 优先基于检索到的知识库内容回答
2. 如果知识库中有相关内容，需要标注参考来源
3. 如果知识库中没有足够相关信息，需明确告知并标注"仅供参考"
4. 回答要结构清晰，逻辑严密
5. 适当引用原文，确保准确性"""


QUERY_UNDERSTAND_PROMPT = """请分析以下用户问题的类型，并返回JSON格式结果：

用户问题：{query}

请判断问题属于哪一类：
- "chitchat": 闲聊、打招呼、问候、感谢、告别等非知识性问题
  示例："你好"、"谢谢"、"再见"、"早上好"、"你是谁"、"怎么样"
- "clear": 知识性问题，表述明确，语义清晰，可以直接检索
  示例："Python中list和tuple的区别是什么？"、"什么是面向对象编程？"
- "vague": 知识性问题，但表述模糊或不完整，需要扩展语义才能有效检索
  示例："那个怎么用？"、"关于机器学习的东西"、"老师讲的那个方法"
- "broad": 知识性问题，但过于宽泛，涵盖多个方面，需要拆分为子问题分别检索
  示例："介绍一下深度学习"、"如何学好编程？"、"Web开发都需要学什么？"

返回格式：{{"type": "chitchat/clear/vague/broad", "sub_questions": ["子问题1", "子问题2"]}}

注意：
- type为chitchat/clear/vague时，sub_questions为空数组
- type为broad时，sub_questions包含3-5个具体子问题
- 只返回JSON，不要其他内容"""


HYPOTHETICAL_DOC_PROMPT = """请针对以下问题，生成一段假设性的文档内容，该文档如果存在，将能完美回答这个问题：

问题：{query}

请直接输出假设性文档内容："""


SUB_QUERY_PROMPT = """请将以下宽泛问题拆分为3-5个具体的子问题，以便进行精确检索：

原问题：{query}

请以JSON数组格式返回子问题列表，如：["子问题1", "子问题2", "子问题3"]
只返回JSON数组，不要其他内容。"""


SUMMARY_PROMPT = """请将以下多轮对话历史压缩为一段简洁的摘要，保留关键信息和上下文：

{conversation}

摘要："""


class QAAgent(BaseAgent):
    agent_type = "qa"
    agent_name = "智能问答助手"
    agent_description = "基于知识库的智能问答，支持RAG检索增强生成"

    def __init__(self):
        self.collection_name = "default"

    async def _understand_query(self, state: AgentState) -> AgentState:
        query = state["query"]
        try:
            result = await LLM.chat(
                messages=[
                    {"role": "system", "content": "你是一个问题分析器，只输出JSON。"},
                    {"role": "user", "content": QUERY_UNDERSTAND_PROMPT.format(query=query)},
                ],
                temperature=0.0,
            )
            json_match = re.search(r'\{[^{}]*\}', result.strip(), re.DOTALL)
            if not json_match:
                raise ValueError(f"未找到有效JSON: {result}")
            analysis = json.loads(json_match.group())
            query_type = analysis.get("type", "clear")
            if query_type not in ("chitchat", "clear", "vague", "broad"):
                logger.warning(f"未知问题类型 '{query_type}'，回退为clear")
                query_type = "clear"
            state["context"]["query_type"] = query_type
            state["context"]["sub_questions"] = analysis.get("sub_questions", [])
        except Exception as e:
            logger.warning(f"问题理解失败: {e}，回退为clear")
            state["context"]["query_type"] = "clear"
            state["context"]["sub_questions"] = []
        return state

    async def _expand_query(self, state: AgentState) -> AgentState:
        query_type = state["context"].get("query_type", "clear")
        query = state["query"]

        if query_type == "vague":
            try:
                hypo_doc = await LLM.chat(
                    messages=[
                        {"role": "system", "content": "你是一个文档生成器。"},
                        {"role": "user", "content": HYPOTHETICAL_DOC_PROMPT.format(query=query)},
                    ],
                    temperature=0.3,
                )
                state["context"]["hyde_query"] = hypo_doc.strip()
            except Exception as e:
                logger.warning(f"HyDE生成失败: {e}，使用原始query")
                state["context"]["hyde_query"] = query

        elif query_type == "broad":
            sub_questions = state["context"].get("sub_questions", [])
            if not sub_questions:
                try:
                    result = await LLM.chat(
                        messages=[
                            {"role": "system", "content": "你是一个问题拆分器，只输出JSON数组。"},
                            {"role": "user", "content": SUB_QUERY_PROMPT.format(query=query)},
                        ],
                        temperature=0.0,
                    )
                    json_match = re.search(r'\[[^\]]*\]', result.strip(), re.DOTALL)
                    if json_match:
                        sub_questions = json.loads(json_match.group())
                    if isinstance(sub_questions, list) and sub_questions:
                        state["context"]["sub_questions"] = sub_questions
                    else:
                        state["context"]["sub_questions"] = [query]
                except Exception as e:
                    logger.warning(f"子问题拆分失败: {e}，使用原始query")
                    state["context"]["sub_questions"] = [query]

        return state

    async def _retrieve(self, state: AgentState) -> AgentState:
        query_type = state["context"].get("query_type", "clear")
        
        if query_type == "chitchat":
            state["context"]["retrieved_docs"] = []
            return state
        
        collections = state["context"].get("collection_names", [])
        all_results = []

        if not collections:
            collections = [self.collection_name]

        bm25 = get_bm25_index()
        for collection in collections:
            await bm25.ensure_index(collection)

            if query_type == "broad" and state["context"].get("sub_questions"):
                for sq in state["context"]["sub_questions"]:
                    sq_bm25_results = bm25.search(collection, sq, top_k=10) if bm25.has_index(collection) else None
                    results = await milvus_hybrid_search(
                        collection, sq, top_k=10, bm25_results=sq_bm25_results
                    )
                    all_results.extend(results)
            elif query_type == "vague" and state["context"].get("hyde_query"):
                hyde_query = state["context"]["hyde_query"]
                results = await milvus_search(collection, hyde_query, top_k=20)
                all_results.extend(results)
                original_bm25_results = bm25.search(collection, state["query"], top_k=20) if bm25.has_index(collection) else None
                original_results = await milvus_hybrid_search(
                    collection, state["query"], top_k=10, bm25_results=original_bm25_results
                )
                all_results.extend(original_results)
            else:
                bm25_results = bm25.search(collection, state["query"], top_k=20) if bm25.has_index(collection) else None
                results = await milvus_hybrid_search(
                    collection, state["query"], top_k=20, bm25_results=bm25_results
                )
                all_results.extend(results)

        seen = set()
        unique_results = []
        for r in all_results:
            key = r.get("chunk_id", r.get("content", "")[:50])
            if key not in seen:
                seen.add(key)
                unique_results.append(r)

        state["context"]["retrieved_docs"] = unique_results
        return state

    async def _rerank(self, state: AgentState) -> AgentState:
        docs = state["context"].get("retrieved_docs", [])
        if not docs:
            state["context"]["reranked_docs"] = []
            state["context"]["confidence"] = 0.0
            return state

        query = state["query"]
        reranked = rerank_with_metadata(query, docs, content_key="content", top_k=3)
        
        relevant_docs = [d for d in reranked if d.get("rerank_score", 0) >= 0.5]
        
        if relevant_docs:
            state["context"]["reranked_docs"] = relevant_docs
            max_score = max(d["rerank_score"] for d in relevant_docs)
            state["context"]["confidence"] = min(max_score, 1.0)
        else:
            state["context"]["reranked_docs"] = []
            state["context"]["confidence"] = 0.0

        return state

    async def _generate(self, state: AgentState) -> AgentState:
        query_type = state["context"].get("query_type", "clear")
        docs = state["context"].get("reranked_docs", [])
        confidence = state["context"].get("confidence", 0.0)

        context_text = ""
        sources_set = set()
        
        if query_type != "chitchat":
            for i, doc in enumerate(docs):
                context_text += f"\n[参考文档{i+1}] {doc['content']}\n"
                if doc.get("metadata", {}).get("source"):
                    sources_set.add(doc["metadata"]["source"])
        
        sources = list(sources_set)

        confidence_note = ""
        
        if query_type == "chitchat":
            confidence = 1.0
            system_prompt = "你是一个友好的AI助手，请用温暖、亲切的方式简短回答用户的问题。记住之前的对话内容，保持上下文连贯。"
            messages = [{"role": "system", "content": system_prompt}]
            history = state.get("messages", [])
            if history:
                messages.extend(history[-10:])
            messages.append({"role": "user", "content": state["query"]})
            answer = await LLMFactory.chat(messages, temperature=0.7)
        elif confidence < 0.5 or not docs:
            confidence_note = "\n\n⚠️ 以上回答仅供参考，知识库中相关信息有限，建议进一步确认。"
            messages, summary = await self.format_messages_async(state)
            if summary:
                state["context"]["conversation_summary"] = summary
            if context_text:
                messages[-1]["content"] = (
                    f"基于以下知识库内容回答问题：\n{context_text}\n\n"
                    f"用户问题：{state['query']}"
                )
            else:
                messages[-1]["content"] = state["query"]
            answer = await LLMFactory.chat(messages, temperature=0.3)
            answer = answer + confidence_note
        elif confidence >= 0.7 and sources:
            confidence_note = "\n\n📚 参考来源：" + "、".join(sources)
            messages, summary = await self.format_messages_async(state)
            if summary:
                state["context"]["conversation_summary"] = summary
            messages[-1]["content"] = (
                f"基于以下知识库内容回答问题：\n{context_text}\n\n"
                f"用户问题：{state['query']}"
            )
            answer = await LLMFactory.chat(messages, temperature=0.3)
            answer = answer + confidence_note
        else:
            messages, summary = await self.format_messages_async(state)
            if summary:
                state["context"]["conversation_summary"] = summary
            messages[-1]["content"] = (
                f"基于以下知识库内容回答问题：\n{context_text}\n\n"
                f"用户问题：{state['query']}"
            )
            answer = await LLMFactory.chat(messages, temperature=0.3)

        state["final_answer"] = answer
        state["confidence"] = confidence

        if query_type != "chitchat" and (confidence < 0.5 or not docs):
            state["context"]["knowledge_gap"] = True

        return state

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("understand_query", self._understand_query)
        graph.add_node("expand_query", self._expand_query)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("rerank", self._rerank)
        graph.add_node("generate", self._generate)

        graph.set_entry_point("understand_query")
        graph.add_edge("understand_query", "expand_query")
        graph.add_edge("expand_query", "retrieve")
        graph.add_edge("retrieve", "rerank")
        graph.add_edge("rerank", "generate")
        graph.add_edge("generate", END)

        return graph.compile()

    async def run(self, state: AgentState) -> AgentState:
        if "context" not in state:
            state["context"] = {}
        graph = self._build_graph()
        result = await graph.ainvoke(state)
        return result

    async def stream(self, state: AgentState) -> AsyncIterator[str]:
        if "context" not in state:
            state["context"] = {}

        state = await self._understand_query(state)
        
        query_type = state["context"].get("query_type", "clear")
        
        if query_type == "chitchat":
            system_prompt = "你是一个友好的AI助手，请用温暖、亲切的方式简短回答用户的问题。记住之前的对话内容，保持上下文连贯。"
            messages = [{"role": "system", "content": system_prompt}]
            history = state.get("messages", [])
            if history:
                messages.extend(history[-10:])
            messages.append({"role": "user", "content": state["query"]})
            
            state["confidence"] = 1.0
            
            async for chunk in LLMFactory.chat_stream(messages, temperature=0.7):
                yield chunk
            yield json.dumps({"confidence": 1.0, "query_type": "chitchat"}, ensure_ascii=False)
            return
        
        state = await self._expand_query(state)
        state = await self._retrieve(state)
        state = await self._rerank(state)

        docs = state["context"].get("reranked_docs", [])
        confidence = state["context"].get("confidence", 0.0)
        context_text = ""
        sources_set = set()
        for i, doc in enumerate(docs):
            context_text += f"\n[参考文档{i+1}] {doc['content']}\n"
            if doc.get("metadata", {}).get("source"):
                sources_set.add(doc["metadata"]["source"])
        
        sources = list(sources_set)

        messages, summary = await self.format_messages_async(state)
        if context_text:
            messages[-1]["content"] = (
                f"基于以下知识库内容回答问题：\n{context_text}\n\n"
                f"用户问题：{state['query']}"
            )
        else:
            messages[-1]["content"] = state["query"]

        async for chunk in LLMFactory.chat_stream(messages, temperature=0.3):
            yield chunk

        if confidence < 0.5 or not docs:
            yield "\n\n⚠️ 以上回答仅供参考，知识库中相关信息有限，建议进一步确认。"
        elif confidence >= 0.7 and sources:
            yield "\n\n📚 参考来源：" + "、".join(sources)
        
        yield json.dumps({"confidence": confidence, "query_type": query_type}, ensure_ascii=False)

    async def summarize_conversation(self, messages: list[dict]) -> str:
        return await self.summarize_messages(messages)
