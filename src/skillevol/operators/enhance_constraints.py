"""Enhance constraints operator - strengthens requirements."""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skillevol.core.llm import LLMClient
    from skillevol.core.types import EvalResult


class EnhanceConstraintsOperator:
    """Strengthens constraints and requirements in SKILL.md."""

    def __init__(self, llm_client: "LLMClient"):
        self.llm = llm_client

    def apply(
        self,
        skill_md: str,
        current_result: "EvalResult | None",
        results_history: list["EvalResult"],
    ) -> str:
        prompt = self._build_prompt(skill_md, current_result, results_history)
        result = self.llm.generate(prompt)
        return self._clean_output(result)

    def _build_prompt(
        self,
        skill_md: str,
        current_result: "EvalResult | None",
        results_history: list["EvalResult"],
    ) -> str:
        focus_areas = self._identify_weak_areas(current_result, results_history)

        return f"""Enhance the constraints and requirements in the following SKILL.md.

Focus areas based on evaluation results:
{focus_areas}

Enhancement guidelines:
1. Add specific format requirements (e.g., JSON schema, file naming)
2. Define clear success criteria
3. Specify error handling requirements
4. Add validation checkpoints
5. Make requirements measurable

Keep the enhancements focused - don't add unnecessary complexity.

## Original SKILL.md
```markdown
{skill_md}
```

Output ONLY the improved SKILL.md with enhanced constraints. Start directly with the content.
"""

    def _identify_weak_areas(
        self,
        current_result: "EvalResult | None",
        results_history: list["EvalResult"],
    ) -> str:
        if not current_result:
            return "- No specific focus area, add general constraints"

        areas = []
        if current_result.pass_rate < 0.4:
            areas.append("- Task may be too ambiguous, add specific requirements")
        if current_result.pass_at_k < 0.5:
            areas.append("- Results are inconsistent, add more specific constraints")
        if current_result.combined_score < 0.5:
            areas.append("- Overall quality needs improvement, add quality criteria")

        return "\n".join(areas) if areas else "- General enhancement only"

    def _clean_output(self, output: str) -> str:
        output = re.sub(r"^```markdown\n?", "", output)
        output = re.sub(r"^```\w*\n?", "", output)
        output = re.sub(r"\n?```$", "", output)
        return output.strip()
