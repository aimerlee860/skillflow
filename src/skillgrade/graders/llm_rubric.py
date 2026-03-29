"""LLM Rubric grader implementation."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage
from rich.console import Console

from .base import BaseGrader
from ..llm.client import LLMClient
from ..types import GraderConfig, GraderResult
from prompts import PromptManager

console = Console()


class LLMGrader(BaseGrader):
    """Grader that uses an LLM to evaluate agent performance against a rubric.

    The rubric defines qualitative criteria for evaluating the agent's approach,
    workflow compliance, efficiency, and code quality.
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        debug_dir: Path | str | None = None,
    ):
        """Initialize the LLM grader.

        Args:
            llm_client: Optional LLM client (creates default if not provided)
            debug_dir: Optional directory to save prompts and responses for debugging.
                      Can also be set via SKILLGRADE_DEBUG_DIR environment variable.
        """
        self.llm_client = llm_client or LLMClient()

        # 优先使用参数，其次使用环境变量
        if debug_dir:
            self.debug_dir = Path(debug_dir)
        elif os.environ.get("SKILLGRADE_DEBUG_DIR"):
            self.debug_dir = Path(os.environ["SKILLGRADE_DEBUG_DIR"])
        else:
            self.debug_dir = None

    async def grade(
        self,
        workspace: Path | str,
        config: GraderConfig,
        logs: list[dict[str, Any]],
        instruction: str | None = None,
        expected: str | None = None,
        expected_trigger: bool = True,
        skill_name: str | None = None,
        skill_summary: str | None = None,
    ) -> GraderResult:
        """Evaluate the agent using LLM-based rubric.

        Args:
            workspace: Path to the workspace directory
            config: Grader configuration with rubric
            logs: Execution logs from the agent
            instruction: User input (task instruction)
            expected: Expected output
            expected_trigger: Whether skill should be triggered
            skill_name: Skill name
            skill_summary: Skill summary/description

        Returns:
            GraderResult with score and reasoning
        """
        # Extract real results from logs
        actual_triggered = self._extract_actual_triggered(logs)
        actual_output = self._extract_actual_output(logs)

        session_transcript = self._build_transcript(logs)
        prompt = self._build_prompt(
            config=config,
            session_transcript=session_transcript,
            actual_triggered=actual_triggered,
            actual_output=actual_output,
            instruction=instruction,
            expected=expected,
            expected_trigger=expected_trigger,
            skill_name=skill_name,
            skill_summary=skill_summary,
        )

        # 生成调试文件名
        timestamp = int(time.time() * 1000)
        task_name = self._extract_task_name(logs) or "unknown"
        trial_index = self._extract_trial_index(logs) or 0

        try:
            response = await self.llm_client.achat([HumanMessage(content=prompt)])
            content = response.content if hasattr(response, "content") else str(response)

            # Parse JSON from response
            score, reasoning = self._parse_response(content)

            # 保存调试信息
            self._save_debug_info(
                task_name=task_name,
                trial_index=trial_index,
                timestamp=timestamp,
                prompt=prompt,
                response=content,
                score=score,
                reasoning=reasoning,
                logs=logs,
            )

            return GraderResult(
                grader_type="llm_rubric",
                score=score,
                weight=config.weight,
                details=f"Score: {score:.2f}",
                reasoning=reasoning,
            )

        except Exception as e:
            # 保存错误信息到调试文件
            self._save_debug_info(
                task_name=task_name,
                trial_index=trial_index,
                timestamp=timestamp,
                prompt=prompt,
                response="",
                score=0.0,
                reasoning=f"Error: {str(e)}",
                logs=logs,
                error=str(e),
            )

            return GraderResult(
                grader_type="llm_rubric",
                score=0.0,
                weight=config.weight,
                details=f"LLM grading error: {str(e)}",
            )

    def _extract_actual_triggered(self, logs: list[dict[str, Any]]) -> bool:
        """Extract actual trigger status from logs.

        Checks if SKILL.md was accessed (skill triggered).

        Args:
            logs: List of log entries

        Returns:
            True if skill was triggered, False otherwise
        """
        for log in logs:
            if log.get("type") == "skill_tracking":
                data = log.get("data", {})
                activation_status = data.get("activationStatus", "")
                # ACCESSED = SKILL.md was read
                # DEEP_USAGE = deep usage of references/scripts
                if activation_status in ("accessed", "deep_usage"):
                    return True
        return False

    def _extract_actual_output(self, logs: list[dict[str, Any]]) -> str:
        """Extract actual output from agent execution logs.

        Args:
            logs: List of log entries

        Returns:
            Agent's final output string
        """
        for log in logs:
            if log.get("type") == "agent_result":
                data = log.get("data", {})
                output = data.get("output", "")
                if output:
                    return output
        return ""

    def _extract_task_name(self, logs: list[dict[str, Any]]) -> str | None:
        """从日志中提取任务名称。"""
        for log in logs:
            if log.get("type") == "agent_start":
                return log.get("data", {}).get("task_name")
        return None

    def _extract_trial_index(self, logs: list[dict[str, Any]]) -> int | None:
        """从日志中提取 trial 索引。"""
        for log in logs:
            if log.get("type") == "agent_start":
                return log.get("data", {}).get("trial_index")
        return None

    def _save_debug_info(
        self,
        task_name: str,
        trial_index: int,
        timestamp: int,
        prompt: str,
        response: str,
        score: float,
        reasoning: str,
        logs: list[dict[str, Any]] | None = None,
        error: str | None = None,
    ) -> None:
        """保存调试信息到文件。

        Args:
            task_name: 任务名称
            trial_index: Trial 索引
            timestamp: 时间戳
            prompt: 发送给 LLM 的 prompt
            response: LLM 的响应
            score: 解析出的分数
            reasoning: 解析出的推理
            logs: Agent 执行日志（完整交互记录）
            error: 可选的错误信息
        """
        if not self.debug_dir:
            return

        try:
            self.debug_dir.mkdir(parents=True, exist_ok=True)

            # 生成文件名
            safe_task_name = re.sub(r"[^\w\-]", "_", task_name)
            filename = f"grader_{safe_task_name}_trial{trial_index}_{timestamp}.md"
            filepath = self.debug_dir / filename

            # 构建完整的交互记录
            agent_transcript = self._build_transcript(logs) if logs else ""

            # 构建调试内容
            content = f"""# LLM Grader Debug Info

## Meta
- **Task**: {task_name}
- **Trial**: {trial_index}
- **Timestamp**: {timestamp}
- **Score**: {score}
- **Error**: {error or "None"}

## Agent 完整交互记录
{agent_transcript}

---

## Grader Reasoning
{reasoning}

## Grader Prompt (发送给评分 LLM)
```
{prompt}
```

## Grader Response (评分 LLM 返回)
```
{response}
```
"""
            filepath.write_text(content, encoding="utf-8")

        except Exception as e:
            # 调试保存失败不应影响正常流程
            console.print(f"[yellow]Warning: Failed to save debug info: {e}[/yellow]")

    def _parse_response(self, content: str) -> tuple[float, str]:
        """Parse JSON response from LLM.

        Args:
            content: Raw response content

        Returns:
            Tuple of (score, reasoning)
        """
        # Try to find JSON in the response
        json_match = re.search(r"\{[^{}]*\"score\"[^{}]*\}", content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                score = float(data.get("score", 0.0))
                reasoning = str(data.get("reasoning", ""))
                return score, reasoning
            except json.JSONDecodeError:
                pass

        # Fallback: try to extract score from text
        score_match = re.search(r"score[:\s]*([0-9.]+)", content, re.IGNORECASE)
        if score_match:
            score = float(score_match.group(1))
            # Try to get reasoning after score
            reasoning = content[score_match.end() :].strip()[:500]
            return score, reasoning

        return 0.0, "Failed to parse LLM response"

    def _build_transcript(self, logs: list[dict[str, Any]]) -> str:
        """Build a session transcript from logs.

        Args:
            logs: List of log entries

        Returns:
            Formatted transcript string
        """
        lines = []
        lines.append("=" * 60)
        lines.append("AGENT EXECUTION TRANSCRIPT")
        lines.append("=" * 60)
        lines.append("")

        for log in logs:
            log_type = log.get("type", "")
            data = log.get("data", {})

            if log_type == "user_input":
                lines.append("### 用户输入")
                lines.append("-" * 40)
                lines.append(data.get("content", ""))
                lines.append("")

            elif log_type == "system_message":
                content = data.get("content", "")
                if content:
                    lines.append("### 系统消息 (Skill 注入)")
                    lines.append("-" * 40)
                    lines.append(content[:3000])  # 限制长度
                    lines.append("")

            elif log_type == "ai_thinking":
                round_num = data.get("round", "?")
                content = data.get("content", "")
                if content:
                    lines.append(f"### AI 思考 (Round {round_num})")
                    lines.append("-" * 40)
                    lines.append(content[:2000])  # 限制长度
                    lines.append("")

            elif log_type == "tool_call_decision":
                round_num = data.get("round", "?")
                tool = data.get("tool", "unknown")
                args = data.get("args", {})
                lines.append(f"### 工具调用决策 (Round {round_num})")
                lines.append("-" * 40)
                lines.append(f"工具: {tool}")
                if args:
                    if isinstance(args, dict):
                        lines.append(f"参数: {json.dumps(args, indent=2, ensure_ascii=False)}")
                    else:
                        lines.append(f"参数: {args}")
                lines.append("")

            elif log_type == "tool_result":
                tool = data.get("tool", "unknown")
                output = data.get("output", "")
                lines.append(f"### 工具执行结果")
                lines.append("-" * 40)
                lines.append(f"工具: {tool}")
                output_text = output[:3000] if len(output) > 3000 else output
                lines.append(f"输出:\n{output_text}")
                lines.append("")

            elif log_type == "tool_call":
                # 兼容旧格式
                tool = data.get("tool", "unknown")
                tool_input = data.get("tool_input", "")
                output = data.get("output", "")

                lines.append(f"### 工具调用 (旧格式)")
                lines.append("-" * 40)
                lines.append(f"工具: {tool}")
                if isinstance(tool_input, dict):
                    lines.append(f"输入: {json.dumps(tool_input, indent=2, ensure_ascii=False)}")
                else:
                    lines.append(f"输入: {tool_input}")
                output_text = output[:2000] if len(output) > 2000 else output
                lines.append(f"输出:\n{output_text}")
                lines.append("")

            elif log_type == "agent_result":
                output = data.get("output", "")
                lines.append("### Agent 最终输出")
                lines.append("-" * 40)
                output_text = output[:3000] if len(output) > 3000 else output
                lines.append(output_text)
                lines.append("")

            elif log_type == "agent_start":
                # 兼容旧格式
                lines.append("### Agent 启动")
                lines.append("-" * 40)
                if "instruction" in data:
                    lines.append(f"指令:\n{data['instruction']}")
                lines.append("")

        return "\n".join(lines)

    def _build_prompt(
        self,
        config: GraderConfig,
        session_transcript: str,
        actual_triggered: bool,
        actual_output: str,
        instruction: str | None = None,
        expected: str | None = None,
        expected_trigger: bool = True,
        skill_name: str | None = None,
        skill_summary: str | None = None,
    ) -> str:
        """Build the grading prompt using unified template.

        使用统一模板拼接所有信息生成完整评估 prompt。

        Args:
            config: Grader configuration with rubric
            session_transcript: Session transcript
            actual_triggered: Whether the skill was actually triggered
            actual_output: Agent's actual output
            instruction: User input (task instruction)
            expected: Expected output
            expected_trigger: Whether skill should be triggered
            skill_name: Skill name
            skill_summary: Skill summary/description

        Returns:
            Complete prompt for the LLM
        """
        # Build unified evaluation rubric with real results
        rubric = self._build_unified_rubric(
            config=config,
            actual_triggered=actual_triggered,
            actual_output=actual_output,
            instruction=instruction,
            expected=expected,
            expected_trigger=expected_trigger,
            skill_name=skill_name,
            skill_summary=skill_summary,
        )

        return PromptManager.get(
            "skillgrade/grader_evaluation",
            rubric=rubric,
            session_transcript=session_transcript,
        )

    def _build_unified_rubric(
        self,
        config: GraderConfig,
        actual_triggered: bool,
        actual_output: str,
        instruction: str | None = None,
        expected: str | None = None,
        expected_trigger: bool = True,
        skill_name: str | None = None,
        skill_summary: str | None = None,
    ) -> str:
        """Build unified evaluation rubric from task context.

        从参数传递的 task context 构建统一评估标准，
        同时包含真实触发状态和真实答案。

        Args:
            config: Grader configuration with rubric
            actual_triggered: Whether the skill was actually triggered
            actual_output: Agent's actual output
            instruction: User input (task instruction)
            expected: Expected output
            expected_trigger: Whether skill should be triggered
            skill_name: Skill name
            skill_summary: Skill summary/description

        Returns:
            Complete evaluation rubric string
        """
        # 触发状态描述
        trigger_expected_desc = "应该触发" if expected_trigger else "不应该触发"
        trigger_actual_desc = "已触发" if actual_triggered else "未触发"

        # 构建统一评估标准
        rubric = PromptManager.get(
            "skillgrade/grader_rubric",
            skill_name=skill_name or "未知技能",
            skill_summary=skill_summary if skill_summary else "无",
            instruction=instruction or "",
            trigger_expected_desc=trigger_expected_desc,
            trigger_actual_desc=trigger_actual_desc,
            expected=expected if expected else "无",
            actual_output=actual_output if actual_output else "（无输出）",
        )
        # 如果有特例化的评估细节（大模型生成的特殊评估要求），追加到评估标准中
        if config.rubric:
            rubric += f"""

## 特例化评估细则

{config.rubric}
"""
        return rubric
