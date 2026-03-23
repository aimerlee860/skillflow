"""LLM Rubric grader implementation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage

from .base import BaseGrader
from ..llm.client import LLMClient
from ..types import GraderConfig, GraderResult


class LLMGrader(BaseGrader):
    """Grader that uses an LLM to evaluate agent performance against a rubric.

    The rubric defines qualitative criteria for evaluating the agent's approach,
    workflow compliance, efficiency, and code quality.
    """

    def __init__(self, llm_client: LLMClient | None = None):
        """Initialize the LLM grader.

        Args:
            llm_client: Optional LLM client (creates default if not provided)
        """
        self.llm_client = llm_client or LLMClient()

    async def grade(
        self,
        workspace: Path | str,
        config: GraderConfig,
        logs: list[dict[str, Any]],
    ) -> GraderResult:
        """Evaluate the agent using LLM-based rubric.

        Args:
            workspace: Path to the workspace directory
            config: Grader configuration with rubric
            logs: Execution logs from the agent

        Returns:
            GraderResult with score and reasoning
        """
        if not config.rubric:
            return GraderResult(
                grader_type="llm_rubric",
                score=0.0,
                weight=config.weight,
                details="No rubric configured",
            )

        session_transcript = self._build_transcript(logs)
        prompt = self._build_prompt(config.rubric, session_transcript)

        try:
            response = await self.llm_client.achat([HumanMessage(content=prompt)])
            content = response.content if hasattr(response, "content") else str(response)

            # Parse JSON from response
            score, reasoning = self._parse_response(content)

            return GraderResult(
                grader_type="llm_rubric",
                score=score,
                weight=config.weight,
                details=f"Score: {score:.2f}",
                reasoning=reasoning,
            )

        except Exception as e:
            return GraderResult(
                grader_type="llm_rubric",
                score=0.0,
                weight=config.weight,
                details=f"LLM grading error: {str(e)}",
            )

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

            if log_type == "agent_start":
                lines.append("--- Agent Started ---")
                if "instruction" in data:
                    lines.append(f"Instruction:\n{data['instruction']}")
                lines.append("")

            elif log_type == "tool_call":
                tool = data.get("tool", "unknown")
                tool_input = data.get("tool_input", "")
                output = data.get("output", "")

                lines.append(f"Tool: {tool}")
                if isinstance(tool_input, dict):
                    lines.append(f"Input: {json.dumps(tool_input, indent=2)}")
                else:
                    lines.append(f"Input: {tool_input}")
                lines.append(
                    f"Output: {output[:500]}..." if len(output) > 500 else f"Output: {output}"
                )
                lines.append("")

            elif log_type == "agent_result":
                output = data.get("output", "")
                lines.append("--- Agent Final Output ---")
                lines.append(output[:1000] if len(output) > 1000 else output)
                lines.append("")

        return "\n".join(lines)

    def _build_prompt(self, rubric: str, transcript: str) -> str:
        """Build the grading prompt.

        Args:
            rubric: The evaluation rubric
            transcript: Session transcript

        Returns:
            Complete prompt for the LLM
        """
        return f"""You are evaluating an AI agent's performance based on a rubric.

## RUBRIC
{rubric}

## SESSION TRANSCRIPT
{transcript}

## INSTRUCTIONS
1. Carefully review the session transcript above
2. Evaluate the agent's performance against the rubric criteria
3. Provide a score between 0.0 and 1.0
4. Explain your reasoning in detail

Note: The agent executes commands in a CLI environment. The Commands Executed section
shows the actual shell commands that were run and their outputs. This is a true
execution trace, not simulated behavior.

Provide your evaluation as a JSON object with:
- "score": A number between 0.0 and 1.0
- "reasoning": Detailed explanation of the score
"""
