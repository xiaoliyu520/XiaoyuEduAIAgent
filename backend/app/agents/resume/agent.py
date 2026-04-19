from typing import AsyncIterator
from langgraph.graph import StateGraph, END
import json
import asyncio

from app.agents.base import BaseAgent, AgentState
from app.services.llm.factory import LLMFactory


RESUME_SYSTEM_PROMPT = """你是一个专业的简历审查专家。你需要从六个维度对简历进行全面评估，并提供具体的修改建议。

六个评估维度：
1. 工作经历评估 - 评估工作经历的描述是否清晰、有逻辑
2. 技能匹配度分析 - 评估技能与目标岗位的匹配程度
3. 项目描述质量评估 - 评估项目描述是否具体、有成果
4. 量化数据完整性检查 - 检查是否有足够的量化数据支撑
5. 格式排版规范性审查 - 审查简历格式是否规范
6. 表达规范性评估 - 评估语言表达是否专业、准确"""


REVIEW_DIMENSION_PROMPTS = {
    "group1": """请评估以下简历的【工作经历】和【技能匹配度】两个维度：

简历内容：
{resume}

请以JSON格式返回评估结果：
{{
  "work_experience": {{
    "score": 0-100,
    "findings": ["发现1", "发现2"],
    "suggestions": [
      {{"original": "原文", "suggestion": "修改建议", "priority": "high/medium/low"}}
    ]
  }},
  "skill_match": {{
    "score": 0-100,
    "findings": ["发现1", "发现2"],
    "suggestions": [
      {{"original": "原文", "suggestion": "修改建议", "priority": "high/medium/low"}}
    ]
  }}
}}""",

    "group2": """请评估以下简历的【项目描述质量】和【量化数据完整性】两个维度：

简历内容：
{resume}

请以JSON格式返回评估结果：
{{
  "project_quality": {{
    "score": 0-100,
    "findings": ["发现1", "发现2"],
    "suggestions": [
      {{"original": "原文", "suggestion": "修改建议", "priority": "high/medium/low"}}
    ]
  }},
  "quantitative_data": {{
    "score": 0-100,
    "findings": ["发现1", "发现2"],
    "suggestions": [
      {{"original": "原文", "suggestion": "修改建议", "priority": "high/medium/low"}}
    ]
  }}
}}""",

    "group3": """请评估以下简历的【格式排版规范性】和【表达规范性】两个维度：

简历内容：
{resume}

请以JSON格式返回评估结果：
{{
  "format_layout": {{
    "score": 0-100,
    "findings": ["发现1", "发现2"],
    "suggestions": [
      {{"original": "原文", "suggestion": "修改建议", "priority": "high/medium/low"}}
    ]
  }},
  "expression_norm": {{
    "score": 0-100,
    "findings": ["发现1", "发现2"],
    "suggestions": [
      {{"original": "原文", "suggestion": "修改建议", "priority": "high/medium/low"}}
    ]
  }}
}}""",
}

SYNTHESIS_PROMPT = """基于以下六个维度的评估结果，生成一份完整的简历审查报告：

评估结果：
{review_results}

请生成包含以下内容的报告：
1. 总体评价（100字以内）
2. 六维度评分汇总
3. 按优先级排列的具体修改建议（高/中/低）
4. 能力雷达图数据（JSON格式，包含六个维度的分数）

请以JSON格式返回：
{{
  "overall_comment": "总体评价",
  "scores": {{
    "work_experience": 0-100,
    "skill_match": 0-100,
    "project_quality": 0-100,
    "quantitative_data": 0-100,
    "format_layout": 0-100,
    "expression_norm": 0-100
  }},
  "total_score": 0-100,
  "suggestions": [
    {{"dimension": "维度", "original": "原文", "suggestion": "修改建议", "priority": "high/medium/low"}}
  ],
  "radar_data": {{
    "indicators": ["工作经历", "技能匹配", "项目描述", "量化数据", "格式排版", "表达规范"],
    "values": [0, 0, 0, 0, 0, 0]
  }}
}}"""


class ResumeAgent(BaseAgent):
    agent_type = "resume"
    agent_name = "简历审查专家"
    agent_description = "从六个维度全面评估简历，提供具体修改建议和能力雷达图"

    async def _parallel_review(self, state: AgentState) -> AgentState:
        resume_text = state["query"]
        if state.get("context", {}).get("resume_text"):
            resume_text = state["context"]["resume_text"]

        async def review_group(group_name: str, prompt_template: str) -> dict:
            try:
                result = await LLMFactory.chat(
                    messages=[
                        {"role": "system", "content": RESUME_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt_template.format(resume=resume_text)},
                    ],
                    temperature=0.1,
                )
                return json.loads(result.strip())
            except Exception:
                return {group_name: {"score": 0, "findings": [], "suggestions": []}}

        results = await asyncio.gather(
            review_group("group1", REVIEW_DIMENSION_PROMPTS["group1"]),
            review_group("group2", REVIEW_DIMENSION_PROMPTS["group2"]),
            review_group("group3", REVIEW_DIMENSION_PROMPTS["group3"]),
        )

        state["context"]["review_results"] = results
        return state

    async def _synthesize(self, state: AgentState) -> AgentState:
        review_results = state["context"].get("review_results", [])
        results_text = json.dumps(review_results, ensure_ascii=False, indent=2)

        try:
            result = await LLMFactory.chat(
                messages=[
                    {"role": "system", "content": RESUME_SYSTEM_PROMPT},
                    {"role": "user", "content": SYNTHESIS_PROMPT.format(review_results=results_text)},
                ],
                temperature=0.1,
            )
            report = json.loads(result.strip())
            state["context"]["report"] = report
            state["final_answer"] = json.dumps(report, ensure_ascii=False, indent=2)
        except Exception:
            state["final_answer"] = "简历审查报告生成失败，请重试"
            state["context"]["report"] = {}

        return state

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("parallel_review", self._parallel_review)
        graph.add_node("synthesize", self._synthesize)

        graph.set_entry_point("parallel_review")
        graph.add_edge("parallel_review", "synthesize")
        graph.add_edge("synthesize", END)

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
        state = await self._parallel_review(state)
        state = await self._synthesize(state)

        report = state["context"].get("report", {})
        if not report:
            yield state["final_answer"]
            return

        yield "📋 **简历审查报告**\n\n"
        yield f"**总体评价**：{report.get('overall_comment', '')}\n\n"

        scores = report.get("scores", {})
        yield "**维度评分**：\n"
        dim_names = {
            "work_experience": "工作经历",
            "skill_match": "技能匹配",
            "project_quality": "项目描述",
            "quantitative_data": "量化数据",
            "format_layout": "格式排版",
            "expression_norm": "表达规范",
        }
        for key, name in dim_names.items():
            score = scores.get(key, 0)
            yield f"- {name}：{score}/100\n"

        yield f"\n**综合评分**：{report.get('total_score', 0)}/100\n\n"

        suggestions = report.get("suggestions", [])
        if suggestions:
            yield "**修改建议**：\n"
            for i, s in enumerate(suggestions):
                priority = s.get("priority", "medium")
                priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
                yield f"{i+1}. {priority_icon} [{s.get('dimension', '')}] {s.get('suggestion', '')}\n"
                if s.get("original"):
                    yield f"   原文：{s['original']}\n"

        radar = report.get("radar_data", {})
        if radar:
            yield f"\n**雷达图数据**：\n```json\n{json.dumps(radar, ensure_ascii=False, indent=2)}\n```"
