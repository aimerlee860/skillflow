"""Type definitions for skillgrade."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypedDict


class GraderType(str, Enum):
    """Types of graders supported by skillgrade."""

    DETERMINISTIC = "deterministic"
    LLM_RUBRIC = "llm_rubric"
    TRIGGER = "trigger"  # 基于技能追踪数据的触发判定评估器


# =============================================================================
# Skill Analysis Types
# =============================================================================


@dataclass
class SkillMetadata:
    """技能元数据（从 SKILL.md frontmatter 提取）"""

    name: str
    description: str
    compatibility: list[str] = field(default_factory=list)


@dataclass
class SkillSection:
    """技能章节（从 SKILL.md body 提取）"""

    title: str
    content: str
    level: int = 2  # 标题级别 (## = 2, ### = 3)


@dataclass
class SkillResource:
    """技能关联资源"""

    path: str
    type: str  # reference, script, asset
    content: str


@dataclass
class SkillExample:
    """技能示例"""

    name: str
    input: str
    expected_output: str | None = None


@dataclass
class WorkflowStep:
    """工作流程步骤"""

    name: str
    description: str
    order: int


@dataclass
class SkillAnalysis:
    """技能分析结果"""

    metadata: SkillMetadata
    sections: list[SkillSection] = field(default_factory=list)
    resources: list[SkillResource] = field(default_factory=list)

    # 提取的关键信息
    use_cases: list[str] = field(default_factory=list)  # 何时使用
    core_functions: list[str] = field(default_factory=list)  # 核心功能
    workflows: list[WorkflowStep] = field(default_factory=list)  # 工作流程
    validation_rules: list[str] = field(default_factory=list)  # 验证规则
    examples: list[SkillExample] = field(default_factory=list)  # 示例
    error_conditions: list[str] = field(default_factory=list)  # 错误处理条件
    security_notes: list[str] = field(default_factory=list)  # 安全注意事项
    output_formats: list[str] = field(default_factory=list)  # 输出格式

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "metadata": {
                "name": self.metadata.name,
                "description": self.metadata.description,
                "compatibility": self.metadata.compatibility,
            },
            "sections": [
                {"title": s.title, "content": s.content, "level": s.level}
                for s in self.sections
            ],
            "resources": [
                {"path": r.path, "type": r.type, "content": r.content}
                for r in self.resources
            ],
            "useCases": self.use_cases,
            "coreFunctions": self.core_functions,
            "workflows": [
                {"name": w.name, "description": w.description, "order": w.order}
                for w in self.workflows
            ],
            "validationRules": self.validation_rules,
            "examples": [
                {"name": e.name, "input": e.input, "expectedOutput": e.expected_output}
                for e in self.examples
            ],
            "errorConditions": self.error_conditions,
            "securityNotes": self.security_notes,
            "outputFormats": self.output_formats,
        }


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
    expected_trigger: bool | None = None  # 用于 TriggerGrader


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
    # Agent 交互日志类型
    USER_INPUT = "user_input"
    SYSTEM_MESSAGE = "system_message"
    AI_THINKING = "ai_thinking"
    TOOL_CALL_DECISION = "tool_call_decision"
    TOOL_RESULT = "tool_result"


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
    instruction: str | None = None
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
        if self.instruction:
            result["instruction"] = self.instruction
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
    expected: str | None = None  # 期望结果（用于输出对比）
    expected_trigger: bool = True  # 是否应该触发技能
    workspace: list[WorkspaceFile] = field(default_factory=list)
    graders: list[GraderConfig] = field(default_factory=list)
    trials: int = 5
    timeout: int = 300
    agent: str | None = None
    provider: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for LangGraph serialization."""
        result = {
            "name": self.name,
            "instruction": self.instruction,
            "expected": self.expected,
            "expectedTrigger": self.expected_trigger,
            "workspace": [{"src": w.src, "dest": w.dest, "chmod": w.chmod} for w in self.workspace],
            "graders": [
                {
                    "type": g.type.value,
                    "run": g.run,
                    "rubric": g.rubric,
                    "weight": g.weight,
                    "model": g.model,
                    "setup": g.setup,
                    "expectedTrigger": g.expected_trigger,
                }
                for g in self.graders
            ],
            "trials": self.trials,
            "timeout": self.timeout,
        }
        if self.agent:
            result["agent"] = self.agent
        if self.provider:
            result["provider"] = self.provider
        return result


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
    agent_model: str
    agent_timeout: int
    llm_base_url: str
    llm_api_key: str
