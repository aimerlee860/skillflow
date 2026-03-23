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
            analysis = f"""
## Current Performance
- pass_rate: {current_result.pass_rate:.2%}
- pass_at_k: {current_result.pass_at_k:.2%}
- combined_score: {current_result.combined_score:.3f}

Focus on clarifying the parts that are likely causing low scores.
"""

        return f"""Improve the clarity of the following SKILL.md. Focus on:
1. Making instructions unambiguous
2. Using clear, action-oriented language
3. Breaking complex tasks into steps
4. Defining technical terms

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
