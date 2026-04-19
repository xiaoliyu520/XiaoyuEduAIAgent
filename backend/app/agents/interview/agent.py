from typing import AsyncIterator
from langgraph.graph import StateGraph, END
import json

from app.agents.base import BaseAgent, AgentState
from app.services.llm.factory import LLMFactory


INTERVIEW_SYSTEM_PROMPT = """你是一个专业的模拟面试官。你需要根据学员的简历和面试阶段，提出有针对性的问题，并评估学员的回答。

面试流程分为四个阶段：
1. INTRO - 自我介绍阶段：让学员进行自我介绍
2. TECH - 技术问题阶段：针对简历中的技术栈提问
3. PROJECT - 项目经验阶段：深入询问项目细节
4. REPORT - 面试报告阶段：生成面试评估报告

评估维度：
- 技术深度：评估回答的技术深度和准确性
- 表达能力：评估回答的逻辑性和表达清晰度

每个维度独立评分（0-100分）。"""


INTRO_PROMPT = """你是一位面试官，请开始模拟面试。

学员简历摘要：
{resume_summary}

请用友好专业的语气邀请学员进行自我介绍，并简要说明面试流程。"""


TECH_QUESTION_PROMPT = """基于学员的简历和之前的回答，提出一个技术问题。

学员简历摘要：
{resume_summary}

之前的问答记录：
{qa_history}

要求：
1. 针对简历中提到的技术栈提问
2. 优先针对薄弱点出题
3. 不要重复之前的问题
4. 问题难度适中，由浅入深

请直接提出问题，不要其他内容。"""


TECH_EVAL_PROMPT = """请评估学员对以下技术问题的回答：

问题：{question}
学员回答：{answer}

请以JSON格式返回评估结果：
{{
  "tech_score": 0-100,
  "expression_score": 0-100,
  "feedback": "简短反馈",
  "key_points": ["关键点1", "关键点2"],
  "missed_points": ["遗漏点1", "遗漏点2"]
}}"""


PROJECT_QUESTION_PROMPT = """基于学员的简历和之前的回答，提出一个关于项目经验的问题。

学员简历摘要：
{resume_summary}

之前的问答记录：
{qa_history}

要求：
1. 针对简历中的具体项目提问
2. 关注项目中的技术决策和问题解决过程
3. 不要重复之前的问题

请直接提出问题。"""


PROJECT_EVAL_PROMPT = """请评估学员对以下项目经验问题的回答：

问题：{question}
学员回答：{answer}

请以JSON格式返回评估结果：
{{
  "tech_score": 0-100,
  "expression_score": 0-100,
  "feedback": "简短反馈",
  "depth_analysis": "技术深度分析",
  "expression_analysis": "表达分析"
}}"""


REPORT_PROMPT = """请基于以下面试记录生成完整的面试评估报告：

学员简历摘要：{resume_summary}

面试问答记录：
{qa_history}

各轮评分：
{scores}

请以JSON格式返回报告：
{{
  "overall_comment": "总体评价",
  "tech_score": 0-100,
  "expression_score": 0-100,
  "overall_score": 0-100,
  "strengths": ["优势1", "优势2"],
  "weaknesses": ["不足1", "不足2"],
  "suggestions": ["建议1", "建议2"],
  "radar_data": {{
    "indicators": ["技术深度", "表达能力", "项目经验", "问题解决", "逻辑思维", "沟通技巧"],
    "values": [0, 0, 0, 0, 0, 0]
  }},
  "detailed_feedback": "详细反馈"
}}"""


class InterviewAgent(BaseAgent):
    agent_type = "interview"
    agent_name = "模拟面试官"
    agent_description = "四阶段模拟面试，支持动态出题和双轨评估"

    STAGES = ["INTRO", "TECH", "PROJECT", "REPORT"]
    TECH_QUESTIONS_COUNT = 3
    PROJECT_QUESTIONS_COUNT = 2

    async def _intro(self, state: AgentState) -> AgentState:
        resume_summary = state.get("context", {}).get("resume_summary", "暂无简历信息")
        response = await LLMFactory.chat(
            messages=[
                {"role": "system", "content": INTERVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": INTRO_PROMPT.format(resume_summary=resume_summary)},
            ],
            temperature=0.7,
        )
        state["final_answer"] = response
        state["context"]["stage"] = "INTRO"
        state["context"]["qa_history"] = []
        state["context"]["scores"] = []
        state["context"]["question_count"] = 0
        return state

    async def _tech_question(self, state: AgentState) -> AgentState:
        resume_summary = state.get("context", {}).get("resume_summary", "")
        qa_history = self._format_qa_history(state.get("context", {}).get("qa_history", []))

        response = await LLMFactory.chat(
            messages=[
                {"role": "system", "content": INTERVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": TECH_QUESTION_PROMPT.format(
                    resume_summary=resume_summary, qa_history=qa_history
                )},
            ],
            temperature=0.7,
        )
        state["final_answer"] = response
        state["context"]["current_question"] = response
        state["context"]["stage"] = "TECH"
        return state

    async def _tech_evaluate(self, state: AgentState) -> AgentState:
        current_q = state.get("context", {}).get("current_question", "")
        answer = state["query"]

        try:
            result = await LLMFactory.chat(
                messages=[
                    {"role": "system", "content": INTERVIEW_SYSTEM_PROMPT},
                    {"role": "user", "content": TECH_EVAL_PROMPT.format(
                        question=current_q, answer=answer
                    )},
                ],
                temperature=0.1,
            )
            eval_result = json.loads(result.strip())
        except Exception:
            eval_result = {
                "tech_score": 50,
                "expression_score": 50,
                "feedback": "评估完成",
                "key_points": [],
                "missed_points": [],
            }

        state["context"]["qa_history"].append({
            "stage": "TECH",
            "question": current_q,
            "answer": answer,
            "eval": eval_result,
        })
        state["context"]["scores"].append(eval_result)
        state["context"]["question_count"] = state["context"].get("question_count", 0) + 1

        feedback = eval_result.get("feedback", "")
        state["final_answer"] = f"感谢你的回答。{feedback}"

        if state["context"]["question_count"] >= self.TECH_QUESTIONS_COUNT:
            state["context"]["stage"] = "PROJECT"
            state["context"]["question_count"] = 0

        return state

    async def _project_question(self, state: AgentState) -> AgentState:
        resume_summary = state.get("context", {}).get("resume_summary", "")
        qa_history = self._format_qa_history(state.get("context", {}).get("qa_history", []))

        response = await LLMFactory.chat(
            messages=[
                {"role": "system", "content": INTERVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": PROJECT_QUESTION_PROMPT.format(
                    resume_summary=resume_summary, qa_history=qa_history
                )},
            ],
            temperature=0.7,
        )
        state["final_answer"] = response
        state["context"]["current_question"] = response
        state["context"]["stage"] = "PROJECT"
        return state

    async def _project_evaluate(self, state: AgentState) -> AgentState:
        current_q = state.get("context", {}).get("current_question", "")
        answer = state["query"]

        try:
            result = await LLMFactory.chat(
                messages=[
                    {"role": "system", "content": INTERVIEW_SYSTEM_PROMPT},
                    {"role": "user", "content": PROJECT_EVAL_PROMPT.format(
                        question=current_q, answer=answer
                    )},
                ],
                temperature=0.1,
            )
            eval_result = json.loads(result.strip())
        except Exception:
            eval_result = {
                "tech_score": 50,
                "expression_score": 50,
                "feedback": "评估完成",
                "depth_analysis": "",
                "expression_analysis": "",
            }

        state["context"]["qa_history"].append({
            "stage": "PROJECT",
            "question": current_q,
            "answer": answer,
            "eval": eval_result,
        })
        state["context"]["scores"].append(eval_result)
        state["context"]["question_count"] = state["context"].get("question_count", 0) + 1

        feedback = eval_result.get("feedback", "")
        state["final_answer"] = f"感谢你的回答。{feedback}"

        if state["context"]["question_count"] >= self.PROJECT_QUESTIONS_COUNT:
            state["context"]["stage"] = "REPORT"

        return state

    async def _generate_report(self, state: AgentState) -> AgentState:
        resume_summary = state.get("context", {}).get("resume_summary", "")
        qa_history = self._format_qa_history(state.get("context", {}).get("qa_history", []))
        scores_text = json.dumps(state.get("context", {}).get("scores", []), ensure_ascii=False, indent=2)

        try:
            result = await LLMFactory.chat(
                messages=[
                    {"role": "system", "content": INTERVIEW_SYSTEM_PROMPT},
                    {"role": "user", "content": REPORT_PROMPT.format(
                        resume_summary=resume_summary,
                        qa_history=qa_history,
                        scores=scores_text,
                    )},
                ],
                temperature=0.1,
            )
            report = json.loads(result.strip())
            state["context"]["report"] = report
            state["final_answer"] = json.dumps(report, ensure_ascii=False, indent=2)
        except Exception:
            state["final_answer"] = "面试报告生成失败"
            state["context"]["report"] = {}

        state["context"]["stage"] = "REPORT"
        return state

    def _format_qa_history(self, qa_history: list) -> str:
        if not qa_history:
            return "暂无"
        lines = []
        for qa in qa_history:
            lines.append(f"[{qa['stage']}] Q: {qa['question']}")
            lines.append(f"A: {qa['answer']}")
            if qa.get("eval"):
                lines.append(f"评估: 技术{qa['eval'].get('tech_score', 0)} 表达{qa['eval'].get('expression_score', 0)}")
        return "\n".join(lines)

    async def _route_stage(self, state: AgentState) -> str:
        stage = state.get("context", {}).get("stage", "INTRO")
        if stage == "INTRO":
            return "intro"
        elif stage == "TECH":
            question_count = state.get("context", {}).get("question_count", 0)
            if question_count == 0 or state.get("context", {}).get("current_question") is None:
                return "tech_question"
            else:
                return "tech_evaluate"
        elif stage == "PROJECT":
            question_count = state.get("context", {}).get("question_count", 0)
            if question_count == 0 or state.get("context", {}).get("current_question") is None:
                return "project_question"
            else:
                return "project_evaluate"
        elif stage == "REPORT":
            return "generate_report"
        return "intro"

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("intro", self._intro)
        graph.add_node("tech_question", self._tech_question)
        graph.add_node("tech_evaluate", self._tech_evaluate)
        graph.add_node("project_question", self._project_question)
        graph.add_node("project_evaluate", self._project_evaluate)
        graph.add_node("generate_report", self._generate_report)

        graph.set_entry_point("intro")
        graph.add_conditional_edges("intro", lambda s: "tech_question")
        graph.add_conditional_edges("tech_question", lambda s: END)
        graph.add_conditional_edges("tech_evaluate", self._route_after_tech)
        graph.add_conditional_edges("project_question", lambda s: END)
        graph.add_conditional_edges("project_evaluate", self._route_after_project)
        graph.add_conditional_edges("generate_report", lambda s: END)

        return graph.compile()

    @staticmethod
    def _route_after_tech(state: AgentState) -> str:
        if state.get("context", {}).get("stage") == "PROJECT":
            return "project_question"
        return "tech_question"

    @staticmethod
    def _route_after_project(state: AgentState) -> str:
        if state.get("context", {}).get("stage") == "REPORT":
            return "generate_report"
        return "project_question"

    async def run(self, state: AgentState) -> AgentState:
        if "context" not in state:
            state["context"] = {}

        stage = state.get("context", {}).get("stage", "INTRO")

        if stage == "INTRO":
            return await self._intro(state)
        elif stage == "TECH":
            has_current_q = state.get("context", {}).get("current_question") is not None
            if not has_current_q:
                return await self._tech_question(state)
            else:
                state = await self._tech_evaluate(state)
                if state["context"]["stage"] == "PROJECT":
                    state["context"]["current_question"] = None
                    state["context"]["question_count"] = 0
                else:
                    state["context"]["current_question"] = None
                    return await self._tech_question(state)
                return await self._project_question(state)
        elif stage == "PROJECT":
            has_current_q = state.get("context", {}).get("current_question") is not None
            if not has_current_q:
                return await self._project_question(state)
            else:
                state = await self._project_evaluate(state)
                if state["context"]["stage"] == "REPORT":
                    return await self._generate_report(state)
                else:
                    state["context"]["current_question"] = None
                    return await self._project_question(state)
        elif stage == "REPORT":
            return await self._generate_report(state)

        return state

    async def stream(self, state: AgentState) -> AsyncIterator[str]:
        result = await self.run(state)
        yield result.get("final_answer", "")
