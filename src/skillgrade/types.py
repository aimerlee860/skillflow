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
    SKILL_TRACKING = "skill_tracking"


class SkillAccessType(str, Enum):
    """Types of skill file access."""

    SKILL_MD = "skill_md"
    REFERENCE = "reference"
    SCRIPT = "script"
    ASSET = "asset"


class SkillActivationStatus(str, Enum):
    """Skill activation status during agent execution."""

    INJECTED = "injected"
    ACCESSED = "accessed"
    DEEP_USAGE = "deep_usage"


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
class SkillAccessRecord:
    """Record of a single skill file access."""

    skill_name: str
    access_type: SkillAccessType
    file_path: str
    timestamp: float
    tool_used: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "skillName": self.skill_name,
            "accessType": self.access_type.value,
            "filePath": self.file_path,
            "timestamp": self.timestamp,
            "toolUsed": self.tool_used,
        }


@dataclass
class SkillTrackingSession:
    """Complete skill tracking data for a single trial."""

    trial_index: int
    skill_name: str
    skill_path: str
    activation_status: SkillActivationStatus
    injected_in_prompt: bool
    access_records: list[SkillAccessRecord] = field(default_factory=list)
    access_depth: int = 0
    first_access_time: float | None = None
    last_access_time: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "trialIndex": self.trial_index,
            "skillName": self.skill_name,
            "skillPath": self.skill_path,
            "activationStatus": self.activation_status.value,
            "injectedInPrompt": self.injected_in_prompt,
            "accessRecords": [r.to_dict() for r in self.access_records],
            "accessDepth": self.access_depth,
            "firstAccessTime": self.first_access_time,
            "lastAccessTime": self.last_access_time,
        }


@dataclass
class SkillTrackingReport:
    """Aggregated skill tracking statistics across all trials."""

    skill_name: str
    total_trials: int
    injected_count: int
    accessed_count: int
    deep_usage_count: int
    access_rate: float
    deep_usage_rate: float
    false_positive_rate: float
    effective_usage_rate: float
    skill_md_reads: int
    reference_reads: int
    script_accesses: int
    asset_accesses: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "skillName": self.skill_name,
            "totalTrials": self.total_trials,
            "injectedCount": self.injected_count,
            "accessedCount": self.accessed_count,
            "deepUsageCount": self.deep_usage_count,
            "accessRate": self.access_rate,
            "deepUsageRate": self.deep_usage_rate,
            "falsePositiveRate": self.false_positive_rate,
            "effectiveUsageRate": self.effective_usage_rate,
            "skillMdReads": self.skill_md_reads,
            "referenceReads": self.reference_reads,
            "scriptAccesses": self.script_accesses,
            "assetAccesses": self.asset_accesses,
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
    skill_tracking: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self, include_logs: bool = False) -> dict[str, Any]:
        """Convert to dictionary with camelCase keys.

        Args:
            include_logs: Whether to include detailed logs (default: False for compact output)
        """
        result: dict[str, Any] = {
            "trialIndex": self.trial_index,
            "reward": self.reward,
            "graders": [g.to_dict() for g in self.graders],
            "durationMs": self.duration_ms,
        }
        if include_logs:
            result["logs"] = [l.to_dict() for l in self.logs]
        if self.error:
            result["error"] = self.error
        if self.skill_tracking:
            result["skillTracking"] = self.skill_tracking
        return result


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
    skill_statistics: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self, include_logs: bool = False) -> dict[str, Any]:
        """Convert to dictionary with camelCase keys.

        Args:
            include_logs: Whether to include detailed logs in trials (default: False)
        """
        result = {
            "taskName": self.task_name,
            "passRate": self.pass_rate,
            "passAtK": self.pass_at_k,
            "passPowK": self.pass_pow_k,
            "trials": [t.to_dict(include_logs=include_logs) for t in self.trials],
            "avgDurationMs": self.avg_duration_ms,
            "timestamp": self.timestamp,
        }
        if self.skill_statistics:
            result["skillStatistics"] = self.skill_statistics
        return result


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
    skill_paths: list[str]
    skill_tracking_enabled: bool
    skill_tracking_reports: list[dict[str, Any]]
