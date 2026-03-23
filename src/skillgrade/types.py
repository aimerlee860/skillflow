"""Type definitions for skillgrade."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypedDict


class GraderType(str, Enum):
    """Types of graders supported by skillgrade."""

    DETERMINISTIC = "deterministic"
    LLM_RUBRIC = "llm_rubric"


@dataclass
class CommandResult:
    """Result of a shell command execution."""

    stdout: str
    stderr: str
    exit_code: int


@dataclass
class GraderConfig:
    """Configuration for a single grader."""

    type: GraderType
    run: str | None = None
    rubric: str | None = None
    weight: float = 1.0
    model: str | None = None
    setup: str | None = None


@dataclass
class GraderResult:
    """Result from a grader evaluation."""

    grader_type: str
    score: float
    weight: float
    details: str
    checks: list[dict[str, Any]] | None = None
    reasoning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with camelCase keys for compatibility."""
        result: dict[str, Any] = {
            "graderType": self.grader_type,
            "score": self.score,
            "weight": self.weight,
            "details": self.details,
        }
        if self.checks:
            result["checks"] = self.checks
        if self.reasoning:
            result["reasoning"] = self.reasoning
        return result


class LogType(str, Enum):
    """Types of log entries."""

    AGENT_START = "agent_start"
    AGENT_ERROR = "agent_error"
    COMMAND = "command"
    AGENT_RESULT = "agent_result"
    GRADER = "grader"
    REWARD = "reward"
    TOOL_CALL = "tool_call"
    SETUP = "setup"
    CLEANUP = "cleanup"


@dataclass
class LogEntry:
    """A single log entry in an evaluation trial."""

    type: LogType
    timestamp: float
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type.value,
            "timestamp": self.timestamp,
            "data": self.data,
        }


@dataclass
class TrialResult:
    """Result of a single trial."""

    task_name: str
    trial_index: int
    reward: float
    graders: list[GraderResult]
    logs: list[LogEntry]
    duration_ms: float
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with camelCase keys."""
        return {
            "taskName": self.task_name,
            "trialIndex": self.trial_index,
            "reward": self.reward,
            "graders": [g.to_dict() for g in self.graders],
            "logs": [l.to_dict() for l in self.logs],
            "durationMs": self.duration_ms,
            "error": self.error,
        }


@dataclass
class EvalReport:
    """Complete evaluation report for a task."""

    task_name: str
    pass_rate: float
    pass_at_k: float
    pass_pow_k: float
    trials: list[TrialResult]
    avg_duration_ms: float
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with camelCase keys."""
        return {
            "taskName": self.task_name,
            "passRate": self.pass_rate,
            "passAtK": self.pass_at_k,
            "passPowK": self.pass_pow_k,
            "trials": [t.to_dict() for t in self.trials],
            "avgDurationMs": self.avg_duration_ms,
            "timestamp": self.timestamp,
        }


@dataclass
class WorkspaceFile:
    """A file mapping for the workspace."""

    src: str
    dest: str
    chmod: str | None = None


@dataclass
class TaskConfig:
    """Configuration for a single evaluation task."""

    name: str
    instruction: str
    workspace: list[WorkspaceFile] = field(default_factory=list)
    graders: list[GraderConfig] = field(default_factory=list)
    trials: int = 5
    timeout: int = 300
    agent: str | None = None
    provider: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for LangGraph serialization."""
        return {
            "name": self.name,
            "instruction": self.instruction,
            "workspace": [{"src": w.src, "dest": w.dest, "chmod": w.chmod} for w in self.workspace],
            "graders": [
                {
                    "type": g.type.value,
                    "run": g.run,
                    "rubric": g.rubric,
                    "weight": g.weight,
                    "model": g.model,
                    "setup": g.setup,
                }
                for g in self.graders
            ],
            "trials": self.trials,
            "timeout": self.timeout,
        }


@dataclass
class EvalConfig:
    """Top-level evaluation configuration."""

    version: str = "1"
    skill: str | None = None
    defaults: dict[str, Any] = field(default_factory=dict)
    tasks: list[TaskConfig] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "version": self.version,
            "skill": self.skill,
            "defaults": self.defaults,
            "tasks": [t.to_dict() for t in self.tasks],
        }


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    name: str
    model: str | None = None
    timeout: int = 300


@dataclass
class EnvironmentConfig:
    """Configuration for the execution environment."""

    skill_paths: list[str] = field(default_factory=list)
    workspace_files: list[WorkspaceFile] = field(default_factory=list)
    cpus: int = 2
    memory_mb: int = 2048


class SmokeState(TypedDict, total=False):
    """LangGraph state for smoke evaluation."""

    task_name: str
    instruction: str
    workspace: str
    grader_configs: list[dict[str, Any]]
    results: list[dict[str, Any]]
    logs: list[dict[str, Any]]
    current_trial: int
    total_trials: int
    start_time: float
    error: str | None
