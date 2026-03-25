"""Clarify operator - improves instruction clarity."""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skillevol.core.llm import LLMClient
    from skillevol.core.types import EvalResult


class ClarifyOperator:
    """Structurally clarifies ambiguous instructions in SKILL.md."""

    def __init__(self, llm_client: "LLMClient"):
        self.llm = llm_client

    def apply(
        self,
        skill_md: str,
        current_result: "EvalResult | None",
        results_history: list["EvalResult"],
    ) -> str:
        prompt = self._build_prompt(skill_md, current_result)
        result = self.llm.generate(prompt)
        return self._clean_output(result)

    def _build_prompt(self, skill_md: str, current_result: "EvalResult | None") -> str:
        analysis = ""
        if current_result:
            issues = current_result.diagnose_issues()
            issues_str = ", ".join(issues) if issues else "None detected"

            analysis = f"""
## Current Performance

### TASK Metrics
- pass_rate: {current_result.pass_rate:.2%} (single trial success)
- pass_at_k: {current_result.pass_at_k:.2%} (at least one success in K trials)
- pass_pow_k: {current_result.pass_pow_k:.2%} (all K trials succeed)
- reward: {current_result.reward:.2f} (weighted average score)

### SKILL Metrics
- access_rate: {current_result.access_rate:.2%} (trigger accuracy)
- deep_usage_rate: {current_result.deep_usage_rate:.2%} (deep usage)
- false_positive_rate: {current_result.false_positive_rate:.2%} (false triggers)
- effective_usage_rate: {current_result.effective_usage_rate:.2%} (effective usage)
- quality_score: {current_result.quality_score:.2f} (overall quality)

### Diagnosed Issues: {issues_str}

### Focus Areas for Clarification:
"""

            # Add specific guidance based on issues
            if "low_reliability" in issues:
                analysis += "- Instructions may be too ambiguous. Add precise definitions.\n"
            if "under_triggering" in issues:
                analysis += "- Trigger conditions unclear. Make WHEN to use this skill explicit.\n"
            if "shallow_usage" in issues:
                analysis += "- Skill content not fully utilized. Clarify how to use each section.\n"
            if "low_quality_output" in issues:
                analysis += "- Output expectations unclear. Define expected output format precisely.\n"

        return f"""Improve the clarity of the following SKILL.md. Focus on:
1. Making instructions unambiguous
2. Using clear, action-oriented language
3. Breaking complex tasks into steps
4. Defining technical terms
5. Making trigger conditions explicit (when to use this skill)
6. Clarifying expected output format

{analysis}
## Original SKILL.md
```markdown
{skill_md}
```

Output ONLY the improved SKILL.md content. Start directly with the content.
"""

    def _clean_output(self, output: str) -> str:
        output = re.sub(r"^```markdown\n?", "", output)
        output = re.sub(r"^```\w*\n?", "", output)
        output = re.sub(r"\n?```$", "", output)
        return output.strip()
