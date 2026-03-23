"""State definitions for LangGraph smoke evaluation."""

from __future__ import annotations

from typing import Any, TypedDict


class SmokeState(TypedDict, total=False):
    """State for the smoke evaluation graph.

    This state is passed through the graph nodes and carries:
    - Task configuration
    - Execution results and logs
    - Trial iteration state
    """

    task_name: str
    instruction: str
    workspace_config: list[dict[str, Any]]
    grader_configs: list[dict[str, Any]]
    skill_paths: list[str]

    results: list[dict[str, Any]]
    logs: list[dict[str, Any]]

    current_trial: int
    total_trials: int
    start_time: float

    error: str | None


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
