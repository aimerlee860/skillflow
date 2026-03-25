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
        issues = current_result.diagnose_issues() if current_result else []
        issues_str = ", ".join(issues) if issues else "None detected"

        performance_context = ""
        if current_result:
            performance_context = f"""
## Current Performance

### TASK Metrics
- pass_rate: {current_result.pass_rate:.2%}
- pass_at_k: {current_result.pass_at_k:.2%}
- pass_pow_k: {current_result.pass_pow_k:.2%}
- reward: {current_result.reward:.2f}

### SKILL Metrics
- access_rate: {current_result.access_rate:.2%}
- deep_usage_rate: {current_result.deep_usage_rate:.2%}
- false_positive_rate: {current_result.false_positive_rate:.2%}
- effective_usage_rate: {current_result.effective_usage_rate:.2%}

### Diagnosed Issues: {issues_str}

### Constraint Focus Areas:
{focus_areas}
"""

        return f"""Enhance the constraints and requirements in the following SKILL.md.

{performance_context}

Enhancement guidelines:
1. Add specific format requirements (e.g., JSON schema, file naming)
2. Define clear success criteria
3. Specify error handling requirements
4. Add validation checkpoints
5. Make requirements measurable
6. Tighten trigger conditions if over-triggering is an issue

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

        # TASK-level issues
        if current_result.pass_rate < 0.4:
            areas.append("- Task may be too ambiguous, add specific requirements")
        if current_result.pass_at_k < 0.5:
            areas.append("- Results are inconsistent, add more specific constraints")
        if current_result.pass_pow_k < 0.3:
            areas.append("- Low consistency, add stricter validation rules")
        if current_result.reward < 0.5:
            areas.append("- Output quality low, add quality criteria")

        # SKILL-level issues
        if current_result.false_positive_rate > 0.3:
            areas.append("- Over-triggering detected, tighten trigger conditions")
        if current_result.access_rate < 0.5:
            areas.append("- Under-triggering, make trigger conditions more explicit")
        if current_result.deep_usage_rate < 0.3:
            areas.append("- Shallow usage, add requirements to use more skill content")
        if current_result.effective_usage_rate < 0.4:
            areas.append("- Ineffective usage, add usage effectiveness criteria")

        return "\n".join(areas) if areas else "- General enhancement only"

    def _clean_output(self, output: str) -> str:
        output = re.sub(r"^```markdown\n?", "", output)
        output = re.sub(r"^```\w*\n?", "", output)
        output = re.sub(r"\n?```$", "", output)
        return output.strip()
