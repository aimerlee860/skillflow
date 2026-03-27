"""State definitions for LangGraph smoke evaluation."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class SmokeState(TypedDict, total=False):
    """State for the smoke evaluation graph.

    This state is passed through the graph nodes and carries:
    - Task configuration
    - Execution results and logs
    - Trial iteration state
    - Skill tracking data
    """

    task_name: str
    instruction: str
    workspace_config: list[dict[str, Any]]
    grader_configs: list[dict[str, Any]]
    skill_paths: list[str]

    # 工作目录（由 setup_node 创建）
    workspace: str

    # 使用 Annotated 和 operator.add 来实现列表追加
    results: Annotated[list[dict[str, Any]], operator.add]
    logs: Annotated[list[dict[str, Any]], operator.add]

    current_trial: int
    total_trials: int
    start_time: float
    trial_start_time: float  # 每个 trial 的开始时间

    error: str | None

    # Skill tracking fields
    skill_tracking_enabled: bool
    skill_tracking_reports: list[dict[str, Any]]

    # Debug directory for saving grader prompts/responses
    debug_dir: str | None


class TrialState(TypedDict, total=False):
    """State for a single trial within the smoke evaluation."""

    task_name: str
    trial_index: int
    instruction: str
    workspace: str
    grader_configs: list[dict[str, Any]]

    agent_output: str | None
    tool_logs: list[dict[str, Any]]
    grader_results: list[dict[str, Any]]
    reward: float | None

    duration_ms: float
    error: str | None

    # Skill tracking data
    skill_tracking: list[dict[str, Any]]
