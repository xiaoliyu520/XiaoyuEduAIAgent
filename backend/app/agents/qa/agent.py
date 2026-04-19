from typing import AsyncIterator
from langgraph.graph import StateGraph, END

from app.agents.base import BaseAgent, AgentState
from app.services.llm.factory import LLMFactory
from app.services.reranker.service import rerank_with_metadata
from app.mcp.milvus.client import search as milvus_search, hybrid_search as milvus_hybrid_search
from app.mcp.milvus.bm25 import get_bm25_index
from app.services.llm.factory import LLMFactory as LLM
import json


QA_SYSTEM_PROMPT = """你是一个专业的教育领域智能问答助手。你的职责是基于知识库内容，准确、专业地回答学员的问题。

回答要求：
1. 优先基于检索到的知识库内容回答
2. 如果知识库中有相关内容，需要标注参考来源
3. 如果知识库中没有足够相关信息，需明确告知并标注"仅供参考"
4. 回答要结构清晰，逻辑严密
5. 适当引用原文，确保准确性"""


QUERY_UNDERSTAND_PROMPT = """请分析以下用户问题的清晰程度，并返回JSON格式结果：

用户问题：{query}

请判断问题属于哪一类：
- "clear": 问题明确，可以直接检索
- "vague": 问题模糊，需要扩展语义
- "broad": 问题过于宽泛，需要拆分为子问题

返回格式：{{"type": "clear/vague/broad", "sub_questions": ["子问题1", "子问题2"], "expanded_query": "扩展后的问题"}}

只返回JSON，不要其他内容。"""


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
            analysis = json.loads(result.strip())
            state["context"]["query_type"] = analysis.get("type", "clear")
            state["context"]["sub_questions"] = analysis.get("sub_questions", [])
            state["context"]["expanded_query"] = analysis.get("expanded_query", query)
        except Exception:
            state["context"]["query_type"] = "clear"
            state["context"]["expanded_query"] = query
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
            except Exception:
                state["context"]["hyde_query"] = query

        elif query_type == "broad":
            try:
                result = await LLM.chat(
                    messages=[
                        {"role": "system", "content": "你是一个问题拆分器，只输出JSON数组。"},
                        {"role": "user", "content": SUB_QUERY_PROMPT.format(query=query)},
                    ],
                    temperature=0.0,
                )
                sub_questions = json.loads(result.strip())
                if isinstance(sub_questions, list):
                    state["context"]["sub_questions"] = sub_questions
            except Exception:
                state["context"]["sub_questions"] = [query]

        return state

    async def _retrieve(self, state: AgentState) -> AgentState:
        query_type = state["context"].get("query_type", "clear")
        collection = state["context"].get("collection_name", self.collection_name)
        all_results = []

        if query_type == "broad" and state["context"].get("sub_questions"):
            for sq in state["context"]["sub_questions"]:
                results = await milvus_search(collection, sq, top_k=10)
                all_results.extend(results)
        elif query_type == "vague" and state["context"].get("hyde_query"):
            hyde_query = state["context"]["hyde_query"]
            results = await milvus_search(collection, hyde_query, top_k=20)
            all_results.extend(results)
            original_results = await milvus_search(collection, state["query"], top_k=10)
            all_results.extend(original_results)
        else:
            bm25 = get_bm25_index()
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
        state["context"]["reranked_docs"] = reranked

        if reranked:
            max_score = max(d["rerank_score"] for d in reranked)
            state["context"]["confidence"] = min(max_score, 1.0)
        else:
            state["context"]["confidence"] = 0.0

        return state

    async def _generate(self, state: AgentState) -> AgentState:
        docs = state["context"].get("reranked_docs", [])
        confidence = state["context"].get("confidence", 0.0)

        context_text = ""
        sources = []
        for i, doc in enumerate(docs):
            context_text += f"\n[参考文档{i+1}] {doc['content']}\n"
            if doc.get("metadata", {}).get("source"):
                sources.append(doc["metadata"]["source"])

        confidence_note = ""
        if confidence < 0.4:
            confidence_note = "\n\n⚠️ 以上回答仅供参考，知识库中相关信息有限，建议进一步确认。"
        elif confidence >= 0.7 and sources:
            confidence_note = "\n\n📚 参考来源：" + "、".join(sources)

        messages = self.format_messages(state)
        if context_text:
            messages[-1]["content"] = (
                f"基于以下知识库内容回答问题：\n{context_text}\n\n"
                f"用户问题：{state['query']}"
            )

        answer = await LLMFactory.chat(messages, temperature=0.3)
        state["final_answer"] = answer + confidence_note
        state["confidence"] = confidence

        if confidence < 0.4:
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
        state = await self._expand_query(state)
        state = await self._retrieve(state)
        state = await self._rerank(state)

        docs = state["context"].get("reranked_docs", [])
        confidence = state["context"].get("confidence", 0.0)
        context_text = ""
        sources = []
        for i, doc in enumerate(docs):
            context_text += f"\n[参考文档{i+1}] {doc['content']}\n"
            if doc.get("metadata", {}).get("source"):
                sources.append(doc["metadata"]["source"])

        messages = self.format_messages(state)
        if context_text:
            messages[-1]["content"] = (
                f"基于以下知识库内容回答问题：\n{context_text}\n\n"
                f"用户问题：{state['query']}"
            )

        async for chunk in LLMFactory.chat_stream(messages, temperature=0.3):
            yield chunk

        if confidence < 0.4:
            yield "\n\n⚠️ 以上回答仅供参考，知识库中相关信息有限，建议进一步确认。"
        elif confidence >= 0.7 and sources:
            yield "\n\n📚 参考来源：" + "、".join(sources)

    async def summarize_conversation(self, messages: list[dict]) -> str:
        conversation_text = "\n".join(
            [f"{m['role']}: {m['content']}" for m in messages]
        )
        summary = await LLM.chat(
            messages=[{"role": "user", "content": SUMMARY_PROMPT.format(conversation=conversation_text)}],
            temperature=0.0,
        )
        return summary.strip()
