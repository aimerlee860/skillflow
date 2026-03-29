"""LLM-based boundary test case generator.

Generates boundary test cases by analyzing SKILL.md through LLM,
identifying boundary conditions such as:
1. Numeric boundaries (min/max values)
2. Input completeness (missing required fields)
3. Format boundaries (invalid formats, special characters)
4. Business-specific boundaries (from skill definition)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from rich.console import Console

from .context import SkillContext
from prompts import PromptManager

console = Console()


@dataclass
class BoundaryTestCase:
    """A boundary test case."""

    name: str
    instruction: str
    expected_trigger: bool
    boundary_type: str  # 数值|完整性|格式|业务
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "instruction": self.instruction,
            "expectedTrigger": self.expected_trigger,
            "boundaryType": self.boundary_type,
            "description": self.description,
        }


class LLMBoundaryGenerator:
    """LLM-based boundary test case generator.

    Uses LLM to identify boundary conditions from skill definition
    and generate appropriate test cases.
    """


    def __init__(self, llm_client: Any = None):
        """Initialize the generator.

        Args:
            llm_client: LLM client for generation
        """
        self.llm_client = llm_client
        self._skill_context: SkillContext | None = None

    def set_skill_context(self, context: SkillContext) -> None:
        """Set skill context for generation.

        Args:
            context: SkillContext extracted from SKILL.md
        """
        self._skill_context = context

    def get_skill_context(self) -> SkillContext | None:
        """Get current skill context."""
        return self._skill_context

    def generate(self, num_cases: int = 3) -> list[BoundaryTestCase]:
        """Generate boundary test cases.

        Args:
            num_cases: Number of boundary cases to generate

        Returns:
            List of BoundaryTestCase
        """
        if not self.llm_client or not self._skill_context:
            return []

        prompt = PromptManager.get(
            "skillgrade/boundary_generation",
            skill_context=self._skill_context.to_prompt_text(),
            num_cases=num_cases,
        )

        try:
            response = self.llm_client.chat.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)
            return self._parse_response(content)
        except Exception as e:
            console.print(f"[yellow]Warning: Boundary case generation failed: {e}[/yellow]")
            return []

    def _parse_response(self, content: str) -> list[BoundaryTestCase]:
        """Parse LLM response to list of BoundaryTestCase."""
        match = re.search(r'\{[\s\S]*\}', content)
        if not match:
            return []

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return []

        cases = []
        for bc in data.get("boundary_cases", []):
            instruction = bc.get("instruction", "")
            if not instruction:
                continue

            cases.append(BoundaryTestCase(
                name=bc.get("name", "边界测试"),
                instruction=instruction,
                expected_trigger=bc.get("expected_trigger", True),
                boundary_type=bc.get("boundary_type", "业务"),
                description=bc.get("description", ""),
            ))

        return cases

    def generate_as_dicts(self, num_cases: int = 3) -> list[dict[str, Any]]:
        """Generate boundary test cases as dictionaries.

        Args:
            num_cases: Number of boundary cases to generate

        Returns:
            List of dicts suitable for TestCase creation
        """
        cases = self.generate(num_cases)
        return [
            {
                "name": case.name,
                "instruction": case.instruction,
                "expected_trigger": case.expected_trigger,
                "source": f"边界测试-{case.boundary_type}",
            }
            for case in cases
        ]
