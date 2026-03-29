"""Type definitions for skillevol."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class OperatorType(Enum):
    CLARIFY = "clarify"
    ADD_EXAMPLES = "add_examples"
    ENHANCE_CONSTRAINTS = "enhance_constraints"
    AUTONOMOUS = "autonomous"


class EvolutionMode(Enum):
    STEADY = "steady"      # Conservative: always evolve from baseline
    GREEDY = "greedy"      # Aggressive: evolve from current best


@dataclass
class EvalResult:
    # TASK-level metrics
    pass_rate: float  # Single trial success rate
    pass_at_k: float  # At least one success in K trials
    pass_pow_k: float = 0.0  # All K trials succeed
    reward: float = 0.0  # Weighted average score

    # SKILL-level metrics
    access_rate: float = 0.0  # Trigger accuracy
    deep_usage_rate: float = 0.0  # Deep usage rate
    false_positive_rate: float = 0.0  # False trigger rate
    effective_usage_rate: float = 0.0  # Effective usage rate
    quality_score: float = 0.0  # Comprehensive quality score

    # Derived metrics
    combined_score: float = 0.0

    # Meta info
    num_trials: int = 0
    num_successes: int = 0
    duration_seconds: float = 0.0
    raw_output: str = ""

    def compute_combined_score(self, weights: dict | None = None) -> float:
        """Compute combined score with configurable weights.

        Default weights prioritize:
        - TASK stability (pass_pow_k): 0.25
        - TASK reliability (pass_at_k): 0.15
        - TASK quality (reward): 0.15
        - SKILL triggering (access_rate, 1 - false_positive_rate): 0.20
        - SKILL usage (effective_usage_rate, deep_usage_rate): 0.15
        - SKILL overall (quality_score): 0.10
        """
        if weights is None:
            weights = {
                "pass_pow_k": 0.25,
                "pass_at_k": 0.15,
                "reward": 0.15,
                "trigger_accuracy": 0.20,  # access_rate * (1 - false_positive_rate)
                "usage_depth": 0.15,  # effective_usage_rate * deep_usage_rate
                "quality_score": 0.10,
            }

        trigger_accuracy = self.access_rate * (1 - self.false_positive_rate)
        usage_depth = self.effective_usage_rate * (1 + self.deep_usage_rate) / 2

        self.combined_score = (
            weights.get("pass_pow_k", 0) * self.pass_pow_k
            + weights.get("pass_at_k", 0) * self.pass_at_k
            + weights.get("reward", 0) * self.reward
            + weights.get("trigger_accuracy", 0) * trigger_accuracy
            + weights.get("usage_depth", 0) * usage_depth
            + weights.get("quality_score", 0) * self.quality_score
        )
        return self.combined_score

    def diagnose_issues(self) -> list[str]:
        """Diagnose issues based on metrics, return list of problem areas."""
        issues = []

        # TASK-level issues
        if self.pass_rate < 0.3:
            issues.append("low_reliability")  # Basic success rate too low
        if self.pass_at_k < 0.5 and self.pass_rate < 0.5:
            issues.append("unstable")  # Inconsistent results
        if self.pass_pow_k < 0.3:
            issues.append("inconsistent")  # Can't consistently succeed
        if self.reward < 0.5 and self.pass_rate > 0.5:
            issues.append("low_quality_output")  # Passes but low quality

        # SKILL-level issues
        if self.false_positive_rate > 0.3:
            issues.append("over_triggering")  # Triggered when shouldn't be
        if self.access_rate < 0.5:
            issues.append("under_triggering")  # Not triggered when should be
        if self.deep_usage_rate < 0.3:
            issues.append("shallow_usage")  # Skill content not fully utilized
        if self.effective_usage_rate < 0.4:
            issues.append("ineffective_usage")  # Low effective usage

        return issues


@dataclass
class ExperimentRecord:
    experiment_id: str
    timestamp: datetime
    operator_type: OperatorType
    # TASK metrics
    pass_rate: float
    pass_at_k: float
    pass_pow_k: float = 0.0
    reward: float = 0.0
    # SKILL metrics
    access_rate: float = 0.0
    deep_usage_rate: float = 0.0
    false_positive_rate: float = 0.0
    effective_usage_rate: float = 0.0
    quality_score: float = 0.0
    # Combined
    combined_score: float = 0.0
    changes_summary: str = ""
    skill_md_before: str = ""
    skill_md_after: str = ""


@dataclass
class ExplorerConfig:
    strategy: str = "hybrid"
    max_structured_attempts: int = 3
    autonomous_threshold: int = 3  # Switch to autonomous after 3 consecutive no-improvements
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.7


@dataclass
class EvalConfig:
    skill_path: Path
    eval_config_path: Path | None = None
    trials: int = 5
    timeout_seconds: int = 300
    threshold: float = 0.5
    skillgrade_cmd: str = "skillflow"  # Use unified skillflow CLI
    parallel: int = 1  # Number of tasks to evaluate in parallel
    skills_path: str | None = None  # Path to skills directory for deepagents


@dataclass
class EvolConfig:
    eval_config: EvalConfig
    explorer_config: ExplorerConfig
    workspace_dir: Path
    results_dir: Path
    max_iterations: int = 100
    max_time_seconds: int = 3600
    patience: int = 20
    program_md_path: Path | None = None


@dataclass
class EvolState:
    current_skill_md: str
    best_skill_md: str
    best_score: float
    baseline_skill_md: str  # Original skill for steady mode
    baseline_score: float   # Original score for steady mode
    iteration: int
    consecutive_no_improve: int
    experiment_history: list[ExperimentRecord] = field(default_factory=list)

    @property
    def should_switch_to_autonomous(self) -> bool:
        return self.consecutive_no_improve >= 3
