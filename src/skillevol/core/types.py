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


@dataclass
class EvalResult:
    pass_rate: float
    pass_at_k: float
    combined_score: float
    num_trials: int
    num_successes: int
    duration_seconds: float
    raw_output: str = ""


@dataclass
class ExperimentRecord:
    experiment_id: str
    timestamp: datetime
    operator_type: OperatorType
    pass_rate: float
    pass_at_k: float
    combined_score: float
    changes_summary: str
    skill_md_before: str = ""
    skill_md_after: str = ""


@dataclass
class ExplorerConfig:
    strategy: str = "hybrid"
    max_structured_attempts: int = 3
    autonomous_threshold: int = 10
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.7


@dataclass
class EvalConfig:
    skill_path: Path
    eval_config_path: Path | None = None
    trials: int = 5
    timeout_seconds: int = 300
    threshold: float = 0.5
    skillgrade_cmd: str = "skillgrade"


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
    iteration: int
    consecutive_no_improve: int
    experiment_history: list[ExperimentRecord] = field(default_factory=list)

    @property
    def should_switch_to_autonomous(self) -> bool:
        return self.consecutive_no_improve >= 10
