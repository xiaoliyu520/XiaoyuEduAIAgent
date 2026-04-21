from typing import AsyncIterator
from langgraph.graph import StateGraph, END
import json
import asyncio
import re
import logging

from app.agents.base import BaseAgent, AgentState
from app.services.llm.factory import LLMFactory

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict:
    text = text.strip()
    if not text:
        raise ValueError("Empty response from LLM")
    
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()
    
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        text = json_match.group()
    
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', text)
    
    return json.loads(text)


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

STREAM_REPORT_PROMPT = """基于以下六个维度的评估结果，请直接输出一份格式化的简历审查报告（使用Markdown格式）：

评估结果：
{review_results}

请按以下格式输出（不要输出JSON，直接输出Markdown）：

**总体评价**：[100字以内的总体评价]

**维度评分**：
- 工作经历：[分数]/100
- 技能匹配：[分数]/100
- 项目描述：[分数]/100
- 量化数据：[分数]/100
- 格式排版：[分数]/100
- 表达规范：[分数]/100

**综合评分**：[总分]/100

🔴 **高优先级修改建议**：
1. [维度] [修改建议]
   原文：[原文内容]

🟡 **中优先级修改建议**：
...

🟢 **低优先级修改建议**：
...

最后单独一行输出雷达图JSON（用于可视化）：
RADAR_JSON: {{"indicators": ["工作经历", "技能匹配", "项目描述", "量化数据", "格式排版", "表达规范"], "values": [分数列表]}}"""


class ResumeAgent(BaseAgent):
    agent_type = "resume"
    agent_name = "简历审查专家"
    agent_description = "从六个维度全面评估简历，提供具体修改建议和能力雷达图"

    async def _parallel_review(self, state: AgentState) -> AgentState:
        resume_text = state["query"]
        if state.get("context", {}).get("resume_text"):
            resume_text = state["context"]["resume_text"]

        logger.info(f"Starting parallel review, resume length: {len(resume_text)}")

        async def review_group(group_name: str, prompt_template: str) -> dict:
            try:
                result = await LLMFactory.chat(
                    messages=[
                        {"role": "system", "content": RESUME_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt_template.format(resume=resume_text)},
                    ],
                    temperature=0.1,
                )
                logger.info(f"{group_name} raw response length: {len(result)}")
                logger.debug(f"{group_name} raw response: {result}")
                parsed = _extract_json(result)
                logger.info(f"{group_name} parsed successfully")
                return parsed
            except Exception as e:
                logger.error(f"{group_name} review failed: {e}", exc_info=True)
                return {group_name: {"score": 0, "findings": [], "suggestions": []}}

        results = await asyncio.gather(
            review_group("group1", REVIEW_DIMENSION_PROMPTS["group1"]),
            review_group("group2", REVIEW_DIMENSION_PROMPTS["group2"]),
            review_group("group3", REVIEW_DIMENSION_PROMPTS["group3"]),
        )

        state["context"]["review_results"] = results
        logger.info(f"Parallel review completed with {len(results)} groups")
        return state

    async def _synthesize(self, state: AgentState) -> AgentState:
        review_results = state["context"].get("review_results", [])
        results_text = json.dumps(review_results, ensure_ascii=False, indent=2)

        logger.info(f"Starting synthesis with {len(review_results)} review results")

        try:
            result = await LLMFactory.chat(
                messages=[
                    {"role": "system", "content": RESUME_SYSTEM_PROMPT},
                    {"role": "user", "content": SYNTHESIS_PROMPT.format(review_results=results_text)},
                ],
                temperature=0.1,
            )
            logger.info(f"Synthesis raw response length: {len(result)}")
            logger.debug(f"Synthesis raw response: {result}")
            report = _extract_json(result)
            state["context"]["report"] = report
            state["final_answer"] = json.dumps(report, ensure_ascii=False, indent=2)
            logger.info("Synthesis completed successfully")
        except Exception as e:
            logger.error(f"Synthesis failed: {e}", exc_info=True)
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
        
        resume_text = state["query"]
        if state.get("context", {}).get("resume_text"):
            resume_text = state["context"]["resume_text"]

        yield "📋 **简历审查报告**\n\n"
        yield "⏳ 正在进行六维度并行评估...\n\n"

        async def review_group(group_name: str, prompt_template: str) -> dict:
            try:
                result = await LLMFactory.chat(
                    messages=[
                        {"role": "system", "content": RESUME_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt_template.format(resume=resume_text)},
                    ],
                    temperature=0.1,
                )
                parsed = _extract_json(result)
                return parsed
            except Exception as e:
                logger.error(f"{group_name} review failed: {e}", exc_info=True)
                return {}

        group_names = {
            "group1": "工作经历、技能匹配",
            "group2": "项目描述、量化数据",
            "group3": "格式排版、表达规范",
        }

        results = []
        for group_key, prompt in REVIEW_DIMENSION_PROMPTS.items():
            result = await review_group(group_key, prompt)
            results.append(result)
            yield f"✅ {group_names[group_key]} 评估完成\n"

        state["context"]["review_results"] = results
        yield "\n⏳ 正在生成综合报告...\n\n"

        results_text = json.dumps(results, ensure_ascii=False, indent=2)
        full_response = ""
        radar_data = None
        in_radar_section = False
        
        try:
            async for chunk in LLMFactory.chat_stream(
                messages=[
                    {"role": "system", "content": RESUME_SYSTEM_PROMPT},
                    {"role": "user", "content": STREAM_REPORT_PROMPT.format(review_results=results_text)},
                ],
                temperature=0.1,
            ):
                full_response += chunk
                
                if "RADAR_JSON" in chunk or in_radar_section:
                    in_radar_section = True
                    continue
                
                if not in_radar_section:
                    yield chunk
            
            if "RADAR_JSON:" in full_response:
                radar_match = re.search(r'RADAR_JSON:\s*(\{[\s\S]*?\})', full_response)
                if radar_match:
                    try:
                        radar_data = json.loads(radar_match.group(1))
                        logger.info(f"Radar data extracted: {radar_data}")
                    except Exception as e:
                        logger.error(f"Failed to parse radar JSON: {e}")
            
            state["context"]["report"] = {
                "radar_data": radar_data,
                "full_response": full_response,
            }
            logger.info(f"Report saved to state with radar_data: {radar_data is not None}")
            
        except Exception as e:
            logger.error(f"Stream synthesis failed: {e}", exc_info=True)
            yield "\n\n简历审查报告生成失败，请重试"
            return
