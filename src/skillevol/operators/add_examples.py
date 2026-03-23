"""Add examples operator - adds relevant examples to SKILL.md."""

import re
from typing import TYPE_CHECKING

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
            performance_context = f"""
## Current Performance
- pass_rate: {current_result.pass_rate:.2%}
- The agent {"struggles with this task" if current_result.pass_rate < 0.5 else "performs reasonably well"}
- Add examples that help agents {"overcome difficulties" if current_result.pass_rate < 0.5 else "achieve higher quality results"}
"""

        return f"""Add {num_examples} high-quality, relevant examples to the following SKILL.md.

Examples should:
1. Be concrete and actionable
2. Show input/output when applicable
3. Demonstrate edge cases
4. Match the style of the existing content

{performance_context}
## Original SKILL.md
```markdown
{skill_md}
```

Output ONLY the improved SKILL.md with examples added. Start directly with the content.
"""

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
