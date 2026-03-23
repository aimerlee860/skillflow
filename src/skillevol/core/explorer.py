"""Explorer - proposes modifications to SKILL.md."""

import re
from pathlib import Path
from typing import Optional

from skillevol.core.llm import LLMClient
from skillevol.core.types import EvalConfig, EvalResult, ExplorerConfig, OperatorType
from skillevol.operators.base import BaseOperator
from skillevol.operators.clarify import ClarifyOperator
from skillevol.operators.add_examples import AddExamplesOperator
from skillevol.operators.enhance_constraints import EnhanceConstraintsOperator


class Explorer:
    def __init__(
        self,
        llm_client: LLMClient,
        config: ExplorerConfig,
        eval_config: EvalConfig,
        program_md: Optional[str] = None,
    ):
        self.llm = llm_client
        self.config = config
        self.eval_config = eval_config
        self.program_md = program_md or self._default_program()
        self._structured_attempts = 0

        self.operators: dict[OperatorType, BaseOperator] = {
            OperatorType.CLARIFY: ClarifyOperator(llm_client),
            OperatorType.ADD_EXAMPLES: AddExamplesOperator(llm_client),
            OperatorType.ENHANCE_CONSTRAINTS: EnhanceConstraintsOperator(llm_client),
        }

    def propose(
        self,
        skill_md: str,
        current_result: Optional[EvalResult],
        results_history: list[EvalResult],
        consecutive_no_improve: int,
    ) -> tuple[str, OperatorType, str]:
        if self._should_use_autonomous(consecutive_no_improve):
            return self._propose_autonomous(skill_md, current_result, results_history)
        return self._propose_structured(skill_md, current_result, results_history)

    def _should_use_autonomous(self, consecutive_no_improve: int) -> bool:
        if self.config.strategy == "autonomous":
            return True
        if self.config.strategy == "hybrid":
            return consecutive_no_improve >= self.config.autonomous_threshold
        return False

    def _propose_structured(
        self,
        skill_md: str,
        current_result: Optional[EvalResult],
        results_history: list[EvalResult],
    ) -> tuple[str, OperatorType, str]:
        operator_types = [
            OperatorType.CLARIFY,
            OperatorType.ADD_EXAMPLES,
            OperatorType.ENHANCE_CONSTRAINTS,
        ]

        op_type = operator_types[self._structured_attempts % len(operator_types)]
        self._structured_attempts += 1

        operator = self.operators[op_type]
        new_skill_md = operator.apply(skill_md, current_result, results_history)
        changes_summary = f"Applied {op_type.value} operator"

        return new_skill_md, op_type, changes_summary

    def _propose_autonomous(
        self,
        skill_md: str,
        current_result: Optional[EvalResult],
        results_history: list[EvalResult],
    ) -> tuple[str, OperatorType, str]:
        history_summary = self._summarize_history(results_history)
        result_summary = (
            self._summarize_result(current_result) if current_result else "No baseline yet"
        )

        prompt = f"""Based on the following information, propose ONE improvement to the SKILL.md file.

## Current SKILL.md
```markdown
{skill_md}
```

## Current Evaluation Result
{result_summary}

## History Summary
{history_summary}

## Program Instructions
{self.program_md}

Please output ONLY the improved SKILL.md content. Do not include any explanations or comments.
Start your response with the full SKILL.md content.
"""

        new_skill_md = self.llm.generate(prompt)
        new_skill_md = self._clean_output(new_skill_md)

        return new_skill_md, OperatorType.AUTONOMOUS, "Autonomous exploration"

    def _summarize_history(self, results: list[EvalResult]) -> str:
        if not results:
            return "No history available yet."

        summaries = []
        for i, r in enumerate(results[-5:], max(1, len(results) - 4)):
            summaries.append(
                f"  - Iteration {i}: pass_rate={r.pass_rate:.2f}, pass_at_k={r.pass_at_k:.2f}, combined={r.combined_score:.3f}"
            )
        return "\n".join(summaries)

    def _summarize_result(self, result: EvalResult) -> str:
        return f"""Current metrics:
  - pass_rate: {result.pass_rate:.2%}
  - pass_at_k: {result.pass_at_k:.2%}
  - combined_score: {result.combined_score:.3f}
  - trials: {result.num_trials} ({result.num_successes} successes)
  - duration: {result.duration_seconds:.1f}s
"""

    def _clean_output(self, output: str) -> str:
        output = re.sub(r"^```markdown\n?", "", output)
        output = re.sub(r"\n?```$", "", output)
        output = re.sub(r"^```\w*\n?", "", output)
        return output.strip()

    def _default_program(self) -> str:
        return """You are optimizing a skill for AI agents. The goal is to maximize the combined score
(pass_rate × (1 + pass_at_k) / 2).

Focus on:
1. Clear task instructions
2. Good examples
3. Specific constraints
4. Edge case handling

Propose ONE improvement at a time. Be conservative - small improvements compound."""
