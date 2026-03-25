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

        # Track operator effectiveness: operator_type -> (successes, total_uses)
        self._operator_stats: dict[OperatorType, tuple[int, int]] = {
            op: (0, 0) for op in OperatorType if op != OperatorType.AUTONOMOUS
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
        op_type = self._select_best_operator(skill_md, current_result, results_history)
        self._structured_attempts += 1

        operator = self.operators[op_type]
        new_skill_md = operator.apply(skill_md, current_result, results_history)
        changes_summary = f"Applied {op_type.value} operator"

        return new_skill_md, op_type, changes_summary

    def _select_best_operator(
        self,
        skill_md: str,
        current_result: Optional[EvalResult],
        results_history: list[EvalResult],
    ) -> OperatorType:
        """Intelligently select the best operator based on current state."""
        scores = self._score_operators(skill_md, current_result, results_history)

        # Prefer operators with proven effectiveness
        for op_type in scores:
            successes, total = self._operator_stats.get(op_type, (0, 0))
            if total > 0:
                success_rate = successes / total
                # Boost score based on historical effectiveness
                scores[op_type] *= (1 + success_rate * 0.5)

        # Filter out operators with zero score (inapplicable)
        valid_scores = {op: score for op, score in scores.items() if score > 0}

        # If all operators are inapplicable, fall back to CLARIFY as safe default
        if not valid_scores:
            return OperatorType.CLARIFY

        # Select operator with highest score
        best_op = max(valid_scores, key=valid_scores.get)
        return best_op

    def _score_operators(
        self,
        skill_md: str,
        current_result: Optional[EvalResult],
        results_history: list[EvalResult],
    ) -> dict[OperatorType, float]:
        """Score each operator based on comprehensive metric analysis."""
        scores = {
            OperatorType.CLARIFY: 1.0,
            OperatorType.ADD_EXAMPLES: 1.0,
            OperatorType.ENHANCE_CONSTRAINTS: 1.0,
        }

        # Detect skill type to skip inapplicable operators
        skill_type = self._detect_skill_type(skill_md)

        # Skip ADD_EXAMPLES for skill types that don't benefit from examples
        if skill_type in ("simple_transform", "validation", "lookup"):
            scores[OperatorType.ADD_EXAMPLES] = 0.0

        # Skip ENHANCE_CONSTRAINTS for already heavily constrained skills
        if skill_type == "heavily_constrained":
            scores[OperatorType.ENHANCE_CONSTRAINTS] = 0.0

        # Analyze current skill content
        has_examples = self._has_examples(skill_md)
        has_constraints = self._has_constraints(skill_md)
        instruction_clarity = self._estimate_clarity(skill_md)

        # Adjust based on content analysis (baseline adjustments)
        if has_examples:
            scores[OperatorType.ADD_EXAMPLES] *= 0.3
        else:
            scores[OperatorType.ADD_EXAMPLES] *= 1.5

        if has_constraints:
            scores[OperatorType.ENHANCE_CONSTRAINTS] *= 0.5
        else:
            scores[OperatorType.ENHANCE_CONSTRAINTS] *= 1.3

        if instruction_clarity > 0.7:
            scores[OperatorType.CLARIFY] *= 0.5
        elif instruction_clarity < 0.4:
            scores[OperatorType.CLARIFY] *= 1.5

        # Use diagnostic analysis if we have evaluation results
        if current_result:
            issues = current_result.diagnose_issues()

            # Map issues to operator adjustments
            issue_operator_boosts = {
                # TASK-level issues
                "low_reliability": {OperatorType.CLARIFY: 2.0, OperatorType.ADD_EXAMPLES: 1.5},
                "unstable": {OperatorType.ADD_EXAMPLES: 2.0, OperatorType.CLARIFY: 1.3},
                "inconsistent": {OperatorType.ENHANCE_CONSTRAINTS: 2.0, OperatorType.ADD_EXAMPLES: 1.5},
                "low_quality_output": {OperatorType.CLARIFY: 1.5, OperatorType.ENHANCE_CONSTRAINTS: 1.3},
                # SKILL-level issues
                "over_triggering": {OperatorType.ENHANCE_CONSTRAINTS: 2.5},  # Need clearer trigger conditions
                "under_triggering": {OperatorType.CLARIFY: 2.0},  # Make trigger conditions more explicit
                "shallow_usage": {OperatorType.ADD_EXAMPLES: 2.0, OperatorType.CLARIFY: 1.5},  # Show how to use skill
                "ineffective_usage": {OperatorType.ADD_EXAMPLES: 2.0, OperatorType.ENHANCE_CONSTRAINTS: 1.5},
            }

            for issue in issues:
                if issue in issue_operator_boosts:
                    for op_type, boost in issue_operator_boosts[issue].items():
                        if op_type in scores and scores[op_type] > 0:
                            scores[op_type] *= boost

            # Additional fine-grained adjustments based on specific metrics

            # Low pass_pow_k: need consistency -> constraints help
            if current_result.pass_pow_k < 0.3:
                scores[OperatorType.ENHANCE_CONSTRAINTS] *= 1.5

            # Low reward but decent pass_rate: output quality issue -> clarify expected output
            if current_result.reward < 0.5 and current_result.pass_rate > 0.5:
                scores[OperatorType.CLARIFY] *= 1.3

            # High false positive: need tighter trigger conditions
            if current_result.false_positive_rate > 0.3:
                scores[OperatorType.ENHANCE_CONSTRAINTS] *= 1.8
                scores[OperatorType.CLARIFY] *= 1.3

            # Low access rate: trigger conditions unclear
            if current_result.access_rate < 0.5:
                scores[OperatorType.CLARIFY] *= 1.8

            # Low deep usage: skill content not being utilized
            if current_result.deep_usage_rate < 0.3:
                scores[OperatorType.ADD_EXAMPLES] *= 1.5
                scores[OperatorType.CLARIFY] *= 1.2

        return scores

    def _detect_skill_type(self, skill_md: str) -> str:
        """Detect the type of skill to determine applicable operators."""
        lower_md = skill_md.lower()

        # Simple data transformation tasks
        transform_keywords = [
            "convert",
            "transform",
            "parse",
            "format",
            "extract",
            "replace",
            "rename",
        ]
        if sum(1 for kw in transform_keywords if kw in lower_md) >= 2:
            return "simple_transform"

        # Validation/checking tasks
        validation_keywords = [
            "validate",
            "check",
            "verify",
            "ensure",
            "confirm",
            "assert",
        ]
        if sum(1 for kw in validation_keywords if kw in lower_md) >= 2:
            return "validation"

        # Lookup/retrieval tasks
        lookup_keywords = [
            "find",
            "search",
            "lookup",
            "retrieve",
            "get",
            "fetch",
        ]
        if sum(1 for kw in lookup_keywords if kw in lower_md) >= 2:
            return "lookup"

        # Check if already heavily constrained
        constraint_count = sum(
            1
            for kw in ["must", "required", "never", "always", "strictly", "mandatory"]
            if kw in lower_md
        )
        if constraint_count >= 5:
            return "heavily_constrained"

        return "general"

    def _has_examples(self, skill_md: str) -> bool:
        """Check if skill has meaningful examples."""
        example_indicators = ["example", "sample", "for instance", "e.g.", "such as"]
        lower_md = skill_md.lower()
        count = sum(1 for ind in example_indicators if ind in lower_md)
        # Also check for code blocks which often contain examples
        code_blocks = skill_md.count("```")
        return count >= 2 or code_blocks >= 2

    def _has_constraints(self, skill_md: str) -> bool:
        """Check if skill has meaningful constraints."""
        constraint_indicators = [
            "must",
            "should",
            "required",
            "never",
            "always",
            "do not",
            "avoid",
            "ensure",
            "constraint",
            "limitation",
        ]
        lower_md = skill_md.lower()
        count = sum(1 for ind in constraint_indicators if ind in lower_md)
        return count >= 3

    def _estimate_clarity(self, skill_md: str) -> float:
        """Estimate instruction clarity (0-1)."""
        lines = skill_md.strip().split("\n")
        non_empty = [l for l in lines if l.strip()]

        if not non_empty:
            return 0.0

        # Heuristics for clarity
        score = 0.5

        # Good: has structure (headers)
        if skill_md.count("#") >= 2:
            score += 0.1

        # Good: reasonable sentence length
        avg_line_len = sum(len(l) for l in non_empty) / len(non_empty)
        if 20 < avg_line_len < 100:
            score += 0.1

        # Bad: very short instructions
        if len(non_empty) < 5:
            score -= 0.2

        # Good: has numbered/bulleted lists
        if any(l.strip().startswith(("1.", "2.", "-", "*", "•")) for l in lines):
            score += 0.1

        return min(1.0, max(0.0, score))

    def record_operator_result(self, op_type: OperatorType, improved: bool) -> None:
        """Record whether an operator improved the skill."""
        if op_type == OperatorType.AUTONOMOUS:
            return
        successes, total = self._operator_stats.get(op_type, (0, 0))
        self._operator_stats[op_type] = (
            successes + (1 if improved else 0),
            total + 1,
        )

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
        issues = result.diagnose_issues()
        issues_str = ", ".join(issues) if issues else "None"

        return f"""Current metrics:

TASK-level:
  - pass_rate: {result.pass_rate:.2%} (single trial success)
  - pass_at_k: {result.pass_at_k:.2%} (at least 1 success in K trials)
  - pass_pow_k: {result.pass_pow_k:.2%} (all K trials succeed)
  - reward: {result.reward:.2f} (weighted average score)

SKILL-level:
  - access_rate: {result.access_rate:.2%} (trigger accuracy)
  - deep_usage_rate: {result.deep_usage_rate:.2%} (deep usage)
  - false_positive_rate: {result.false_positive_rate:.2%} (false triggers)
  - effective_usage_rate: {result.effective_usage_rate:.2%} (effective usage)
  - quality_score: {result.quality_score:.2f} (overall quality)

Combined score: {result.combined_score:.3f}
Diagnosed issues: {issues_str}
Trials: {result.num_trials} ({result.num_successes} successes)
Duration: {result.duration_seconds:.1f}s
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
