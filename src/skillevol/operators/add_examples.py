"""Add examples operator - adds relevant examples to SKILL.md."""

import re
from typing import TYPE_CHECKING

from prompts import PromptManager

if TYPE_CHECKING:
    from skillevol.core.llm import LLMClient
    from skillevol.core.types import EvalResult


class AddExamplesOperator:
    """Adds high-quality examples to SKILL.md."""

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
        num_examples = self._determine_num_examples(results_history)

        performance_context = ""
        if current_result:
            issues = current_result.diagnose_issues()
            issues_str = ", ".join(issues) if issues else "None detected"

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

### Example Strategy:
"""

            # Add specific guidance based on issues
            if "unstable" in issues:
                performance_context += "- Results are inconsistent. Add examples showing correct approach.\n"
            if "shallow_usage" in issues:
                performance_context += "- Skill not fully utilized. Add examples demonstrating full skill usage.\n"
            if "ineffective_usage" in issues:
                performance_context += "- Usage not effective. Add examples of successful task completion.\n"
            if current_result.pass_rate < 0.5:
                performance_context += "- Low success rate. Focus on common failure scenarios.\n"
            else:
                performance_context += "- Decent success rate. Add edge case examples for improvement.\n"

        return PromptManager.get(
            "skillevol/add_examples",
            num_examples=num_examples,
            performance_context=performance_context,
            skill_md=skill_md,
        )

    def _determine_num_examples(self, results_history: list["EvalResult"]) -> int:
        if not results_history:
            return 3
        recent_avg = sum(r.combined_score for r in results_history[-3:]) / min(
            3, len(results_history)
        )
        if recent_avg < 0.3:
            return 5
        elif recent_avg < 0.6:
            return 3
        return 2

    def _clean_output(self, output: str) -> str:
        output = re.sub(r"^```markdown\n?", "", output)
        output = re.sub(r"^```\w*\n?", "", output)
        output = re.sub(r"\n?```$", "", output)
        return output.strip()
