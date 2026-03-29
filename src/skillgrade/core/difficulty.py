"""LLM-based difficulty assessment for test cases.

Assesses test case difficulty based on semantic understanding:
1. Information completeness - does input contain all required fields?
2. Expression clarity - is the user intent clear?
3. Intent clarity - does user know what they want?
4. Skill relevance - how well does it match the skill definition?

Key insight: Short inputs are NOT necessarily easy. Missing key information
is what makes a test case difficult.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ..types import DifficultyLevel
from .context import SkillContext
from prompts import PromptManager


@dataclass
class DifficultyAssessment:
    """Result of difficulty assessment for a test case."""

    level: DifficultyLevel
    score: float  # 0.0-1.0

    # Assessment dimensions
    completeness: float = 0.5      # Information completeness (most important)
    clarity: float = 0.5           # Expression clarity
    intent_clarity: float = 0.5    # Intent clarity
    skill_relevance: float = 0.5   # Skill relevance

    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "level": self.level.value,
            "score": self.score,
            "completeness": self.completeness,
            "clarity": self.clarity,
            "intentClarity": self.intent_clarity,
            "skillRelevance": self.skill_relevance,
            "reasoning": self.reasoning,
        }


class LLMDifficultyAssessor:
    """LLM-based difficulty assessor for test cases.

    Uses LLM to understand semantic meaning of test cases and assess
    difficulty based on information completeness, not just text length.
    """


    def __init__(self, llm_client: Any = None):
        """Initialize the assessor.

        Args:
            llm_client: LLM client for assessment
        """
        self.llm_client = llm_client
        self._skill_context: SkillContext | None = None

    def set_skill_context(self, context: SkillContext) -> None:
        """Set skill context for assessment.

        Args:
            context: SkillContext extracted from SKILL.md
        """
        self._skill_context = context

    def get_skill_context(self) -> SkillContext | None:
        """Get current skill context."""
        return self._skill_context

    def assess(
        self,
        instruction: str,
        expected_trigger: bool = True,
    ) -> DifficultyAssessment:
        """Assess difficulty of a test case.

        Args:
            instruction: User input instruction
            expected_trigger: Whether skill is expected to trigger

        Returns:
            DifficultyAssessment with level, score, and reasoning
        """
        if not self.llm_client or not self._skill_context:
            return self._default_assessment()

        prompt = PromptManager.get(
            "skillgrade/difficulty_assessment",
            skill_context=self._skill_context.to_prompt_text(),
            instruction=instruction,
            expected_trigger="是" if expected_trigger else "否",
        )

        try:
            response = self.llm_client.chat.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            return self._parse_response(content)
        except Exception as e:
            return self._default_assessment(error=str(e))

    def _parse_response(self, content: str) -> DifficultyAssessment:
        """Parse LLM response to DifficultyAssessment."""
        match = re.search(r'\{[\s\S]*\}', content)
        if not match:
            return self._default_assessment(error="No JSON found in response")

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return self._default_assessment(error="Invalid JSON in response")

        # Parse difficulty level
        level_map = {
            "easy": DifficultyLevel.EASY,
            "medium": DifficultyLevel.MEDIUM,
            "hard": DifficultyLevel.HARD,
        }
        level_str = data.get("difficulty", "medium").lower()
        level = level_map.get(level_str, DifficultyLevel.MEDIUM)

        return DifficultyAssessment(
            level=level,
            score=float(data.get("overall_score", 0.5)),
            completeness=float(data.get("completeness", 0.5)),
            clarity=float(data.get("clarity", 0.5)),
            intent_clarity=float(data.get("intent_clarity", 0.5)),
            skill_relevance=float(data.get("skill_relevance", 0.5)),
            reasoning=data.get("reasoning", ""),
        )

    def _default_assessment(self, error: str = "") -> DifficultyAssessment:
        """Return default assessment when LLM is unavailable."""
        return DifficultyAssessment(
            level=DifficultyLevel.MEDIUM,
            score=0.5,
            completeness=0.5,
            clarity=0.5,
            intent_clarity=0.5,
            skill_relevance=0.5,
            reasoning=f"LLM unavailable. {error}".strip(),
        )

    def batch_assess(
        self,
        cases: list[dict[str, Any]],
    ) -> list[DifficultyAssessment]:
        """Assess multiple test cases.

        Args:
            cases: List of dicts with 'instruction' and 'expected_trigger'

        Returns:
            List of DifficultyAssessment results
        """
        return [
            self.assess(
                instruction=case.get("instruction", ""),
                expected_trigger=case.get("expected_trigger", True),
            )
            for case in cases
        ]
