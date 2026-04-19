from typing import AsyncIterator
from langgraph.graph import StateGraph, END
import json

from app.agents.base import BaseAgent, AgentState
from app.services.llm.factory import LLMFactory
from app.mcp.judge0.client import execute_code


CODE_SYSTEM_PROMPT = """你是一个专业的代码审查专家。你需要分析用户提交的代码，识别错误并提供改进建议。

你的分析包括：
1. 语法错误检测 - 检查代码是否存在语法问题
2. 逻辑错误识别 - 分析代码逻辑是否正确
3. 算法复杂度分析 - 评估时间和空间复杂度
4. 代码风格建议 - 提供代码风格改进建议

输出格式要求：
- 使用结构化错误标签，如"空指针异常→数组越界→时间复杂度O(n²)"
- 提供具体的修改建议和修改后的代码"""


CODE_ANALYSIS_PROMPT = """请分析以下{language}代码：

```{language}
{code}
```

沙箱执行结果：
{execution_result}

请以JSON格式返回分析结果：
{{
  "has_error": true/false,
  "error_types": ["错误类型1", "错误类型2"],
  "error_tags": "结构化错误标签（如：语法错误→缩进错误→时间复杂度O(n²)）",
  "syntax_errors": [
    {{
      "line": 行号,
      "description": "错误描述",
      "original": "原始代码",
      "fix": "修复代码"
    }}
  ],
  "logic_errors": [
    {{
      "description": "逻辑错误描述",
      "original": "原始代码",
      "fix": "修复代码",
      "explanation": "修复说明"
    }}
  ],
  "complexity_analysis": {{
    "time_complexity": "O(?)",
    "space_complexity": "O(?)",
    "suggestion": "优化建议"
  }},
  "style_suggestions": [
    {{
      "description": "风格建议",
      "original": "原始代码",
      "improved": "改进代码"
    }}
  ],
  "improved_code": "完整改进后的代码",
  "summary": "总体评价"
}}"""


class CodeAgent(BaseAgent):
    agent_type = "code"
    agent_name = "代码检查专家"
    agent_description = "通过沙箱执行代码，识别语法/逻辑/复杂度问题，输出结构化错误标签"

    async def _execute_code(self, state: AgentState) -> AgentState:
        code = state["query"]
        if state.get("context", {}).get("code"):
            code = state["context"]["code"]
        language = state.get("context", {}).get("language", "python")

        try:
            result = await execute_code(code, language)
            state["context"]["execution_result"] = result
        except Exception as e:
            state["context"]["execution_result"] = {
                "status": "Execution Failed",
                "stderr": str(e),
                "stdout": "",
            }

        return state

    async def _analyze(self, state: AgentState) -> AgentState:
        code = state["query"]
        if state.get("context", {}).get("code"):
            code = state["context"]["code"]
        language = state.get("context", {}).get("language", "python")
        exec_result = state.get("context", {}).get("execution_result", {})

        exec_text = f"状态: {exec_result.get('status', 'Unknown')}\n"
        if exec_result.get("stdout"):
            exec_text += f"标准输出: {exec_result['stdout']}\n"
        if exec_result.get("stderr"):
            exec_text += f"错误输出: {exec_result['stderr']}\n"
        if exec_result.get("compile_output"):
            exec_text += f"编译输出: {exec_result['compile_output']}\n"
        exec_text += f"执行时间: {exec_result.get('time', '0')}s\n"
        exec_text += f"内存使用: {exec_result.get('memory', 0)}KB"

        try:
            result = await LLMFactory.chat(
                messages=[
                    {"role": "system", "content": CODE_SYSTEM_PROMPT},
                    {"role": "user", "content": CODE_ANALYSIS_PROMPT.format(
                        language=language, code=code, execution_result=exec_text
                    )},
                ],
                temperature=0.1,
            )
            analysis = json.loads(result.strip())
            state["context"]["analysis"] = analysis
        except Exception:
            state["context"]["analysis"] = {
                "has_error": True,
                "error_types": ["分析失败"],
                "error_tags": "分析失败",
                "summary": "代码分析过程出现异常，请重试",
            }

        return state

    async def _format_output(self, state: AgentState) -> AgentState:
        analysis = state.get("context", {}).get("analysis", {})
        output_parts = []

        output_parts.append("🔍 **代码检查报告**\n")

        error_tags = analysis.get("error_tags", "无错误")
        output_parts.append(f"**错误标签**：`{error_tags}`\n")

        if analysis.get("has_error"):
            output_parts.append("❌ **发现错误**\n")

            for err in analysis.get("syntax_errors", []):
                output_parts.append(f"- 语法错误（第{err.get('line', '?')}行）：{err.get('description', '')}")
                if err.get("original"):
                    output_parts.append(f"  原始：`{err['original']}`")
                if err.get("fix"):
                    output_parts.append(f"  修复：`{err['fix']}`")

            for err in analysis.get("logic_errors", []):
                output_parts.append(f"- 逻辑错误：{err.get('description', '')}")
                if err.get("explanation"):
                    output_parts.append(f"  说明：{err['explanation']}")
                if err.get("fix"):
                    output_parts.append(f"  修复：`{err['fix']}`")
        else:
            output_parts.append("✅ **未发现语法和逻辑错误**\n")

        complexity = analysis.get("complexity_analysis", {})
        if complexity:
            output_parts.append(f"\n📊 **复杂度分析**：")
            output_parts.append(f"- 时间复杂度：{complexity.get('time_complexity', 'N/A')}")
            output_parts.append(f"- 空间复杂度：{complexity.get('space_complexity', 'N/A')}")
            if complexity.get("suggestion"):
                output_parts.append(f"- 优化建议：{complexity['suggestion']}")

        style_suggestions = analysis.get("style_suggestions", [])
        if style_suggestions:
            output_parts.append(f"\n💡 **风格建议**：")
            for s in style_suggestions:
                output_parts.append(f"- {s.get('description', '')}")
                if s.get("improved"):
                    output_parts.append(f"  改进：`{s['improved']}`")

        if analysis.get("improved_code"):
            output_parts.append(f"\n📝 **改进后代码**：\n```{state.get('context', {}).get('language', 'python')}\n{analysis['improved_code']}\n```")

        if analysis.get("summary"):
            output_parts.append(f"\n📋 **总结**：{analysis['summary']}")

        state["final_answer"] = "\n".join(output_parts)
        return state

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("execute_code", self._execute_code)
        graph.add_node("analyze", self._analyze)
        graph.add_node("format_output", self._format_output)

        graph.set_entry_point("execute_code")
        graph.add_edge("execute_code", "analyze")
        graph.add_edge("analyze", "format_output")
        graph.add_edge("format_output", END)

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
        state = await self._execute_code(state)
        state = await self._analyze(state)
        state = await self._format_output(state)
        yield state.get("final_answer", "")
