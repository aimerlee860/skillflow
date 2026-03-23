"""Base operator class."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skillevol.core.llm import LLMClient
    from skillevol.core.types import EvalResult


class BaseOperator(ABC):
    """Base class for skill modification operators."""

    def __init__(self, llm_client: "LLMClient"):
        self.llm = llm_client

    @abstractmethod
    def apply(
        self,
        skill_md: str,
        current_result: "EvalResult | None",
        results_history: list["EvalResult"],
    ) -> str:
        """Apply this operator to the skill and return the modified version."""
        pass

    def analyze(self, skill_md: str, current_result: "EvalResult | None") -> str:
        """Analyze the current skill and identify issues."""
        if current_result is None:
            return "No baseline evaluation available yet."

        issues = []
        if current_result.pass_rate < 0.5:
            issues.append(
                "- Low pass rate suggests instructions may be unclear or tasks too difficult"
            )
        if current_result.pass_at_k < 0.7:
            issues.append("- Low reliability indicates inconsistent performance")
        if current_result.combined_score < 0.4:
            issues.append("- Overall score is poor, need significant improvements")

        return "\n".join(issues) if issues else "No obvious issues detected."
