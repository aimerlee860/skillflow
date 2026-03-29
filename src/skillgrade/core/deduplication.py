"""LLM-based task deduplication for test cases.

Deduplicates test cases based on TASK similarity, not semantic similarity.
Two test cases are duplicates if they test the same functionality/behavior,
even if the text is different.

Examples:
- "转账100元给张三" vs "转账200元给李四" → same task (both test simple complete transfer)
- "转账100元" vs "转账100元给张三" → different task (missing info vs complete)
- "转账500万" vs "转账100元" → different task (large amount boundary vs normal)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .context import SkillContext
from prompts import PromptManager


@dataclass
class DuplicationCheck:
    """Result of duplication check for a test case."""

    is_duplicate: bool
    same_task: bool
    reasoning: str = ""
    duplicate_of: str | None = None


class LLMTaskDeduplicator:
    """LLM-based task deduplicator.

    Uses LLM to determine if two test cases test the same TASK,
    not just if the text is semantically similar.
    """


    def __init__(self, llm_client: Any = None):
        """Initialize the deduplicator.

        Args:
            llm_client: LLM client for task comparison
        """
        self.llm_client = llm_client
        self._skill_context: SkillContext | None = None

    def set_skill_context(self, context: SkillContext) -> None:
        """Set skill context for deduplication.

        Args:
            context: SkillContext extracted from SKILL.md
        """
        self._skill_context = context

    def get_skill_context(self) -> SkillContext | None:
        """Get current skill context."""
        return self._skill_context

    def deduplicate(
        self,
        cases: list[Any],  # List of TestCase objects
    ) -> tuple[list[Any], list[DuplicationCheck]]:
        """Deduplicate test cases based on task similarity.

        Args:
            cases: List of TestCase objects (must have .name and .instruction)

        Returns:
            Tuple of (deduplicated cases, check results for each input case)
        """
        if len(cases) <= 1:
            return cases, [DuplicationCheck(False, False, "单个用例") for _ in cases]

        context_text = ""
        if self._skill_context:
            context_text = self._skill_context.to_prompt_text()

        kept = [cases[0]]
        checks = [DuplicationCheck(False, False, "首个用例，保留")]

        for case in cases[1:]:
            is_dup = False
            dup_of = None
            check_result = None

            # Compare with all kept cases
            for kept_case in kept:
                check_result = self._check_same_task(
                    context_text,
                    case.instruction,
                    kept_case.instruction,
                )
                if check_result.same_task:
                    is_dup = True
                    dup_of = kept_case.name
                    break

            if is_dup:
                check_result.is_duplicate = True
                check_result.duplicate_of = dup_of
                checks.append(check_result)
            else:
                kept.append(case)
                checks.append(DuplicationCheck(False, False, "不重复，保留"))

        return kept, checks

    def _check_same_task(
        self,
        context: str,
        case_a_instruction: str,
        case_b_instruction: str,
    ) -> DuplicationCheck:
        """Check if two test cases test the same task.

        Args:
            context: Skill context text
            case_a_instruction: First test case instruction
            case_b_instruction: Second test case instruction

        Returns:
            DuplicationCheck with result
        """
        if not self.llm_client:
            return self._fallback_check(case_a_instruction, case_b_instruction)

        prompt = PromptManager.get(
            "skillgrade/task_deduplication",
            skill_context=context,
            case_a=case_a_instruction,
            case_b=case_b_instruction,
        )

        try:
            response = self.llm_client.chat.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            return self._parse_response(content)
        except Exception as e:
            return self._fallback_check(case_a_instruction, case_b_instruction, error=str(e))

    def _parse_response(self, content: str) -> DuplicationCheck:
        """Parse LLM response to DuplicationCheck."""
        match = re.search(r'\{[\s\S]*\}', content)
        if not match:
            return DuplicationCheck(False, False, "解析失败")

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return DuplicationCheck(False, False, "JSON解析失败")

        same_task = data.get("same_task", False)
        return DuplicationCheck(
            is_duplicate=same_task,
            same_task=same_task,
            reasoning=data.get("reasoning", ""),
        )

    def _fallback_check(
        self,
        case_a: str,
        case_b: str,
        error: str = "",
    ) -> DuplicationCheck:
        """Fallback check using simple text similarity.

        This is used when LLM is unavailable.
        """
        # Simple Jaccard similarity as fallback
        set_a = set(case_a.lower())
        set_b = set(case_b.lower())
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        similarity = intersection / union if union > 0 else 0.0

        # Use lower threshold for fallback
        is_similar = similarity > 0.7

        return DuplicationCheck(
            is_duplicate=is_similar,
            same_task=is_similar,
            reasoning=f"文本相似度: {similarity:.0%}. {error}".strip(),
        )
