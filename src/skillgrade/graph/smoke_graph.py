"""Smoke evaluation graph using LangGraph."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from ..core.workspace import create_temp_workspace
from ..types import EvalReport, GraderResult, LogEntry, LogType, TrialResult
from .nodes import (
    cleanup_node,
    grade_node,
    increment_trial,
    run_agent_node,
    setup_node,
    should_continue,
)
from .state import SmokeState


def create_smoke_graph() -> Any:
    """Create the smoke evaluation state graph.

    The graph performs the following workflow:
    1. Setup - Create workspace
    2. Agent - Run the agent
    3. Grade - Evaluate results
    4. Cleanup - Remove workspace
    5. Repeat for N trials

    Returns:
        Compiled LangGraph
    """
    workflow = StateGraph(SmokeState)

    workflow.add_node("setup", setup_node)
    workflow.add_node("agent", run_agent_node)
    workflow.add_node("grade", grade_node)
    workflow.add_node("cleanup", cleanup_node)

    workflow.add_edge(START, "setup")
    workflow.add_edge("setup", "agent")
    workflow.add_edge("agent", "grade")
    workflow.add_edge("grade", "cleanup")

    workflow.add_conditional_edges(
        "cleanup",
        should_continue,
        {
            "setup": "setup",
            "__end__": END,
        },
    )

    return workflow.compile()


async def run_smoke_eval(
    task: dict[str, Any],
    trials: int = 5,
    skill_paths: list[str] | None = None,
    debug_dir: str | None = None,
    skill_name: str | None = None,
    skill_summary: str | None = None,
) -> EvalReport:
    """Run a smoke evaluation for a single task.

    Args:
        task: Task configuration dictionary
        trials: Number of trials to run
        skill_paths: Optional list of skill paths to inject
        debug_dir: Optional directory to save grader prompts/responses for debugging.
                   Can also be set via SKILLGRADE_DEBUG_DIR environment variable.
        skill_name: Optional skill name for grader context
        skill_summary: Optional skill summary for grader context

    Returns:
        EvalReport with aggregated results
    """
    import os

    graph = create_smoke_graph()

    # 优先使用参数，其次使用环境变量
    effective_debug_dir = debug_dir or os.environ.get("SKILLGRADE_DEBUG_DIR")

    initial_state: SmokeState = {
        "task_name": task["name"],
        "instruction": task["instruction"],
        "expected": task.get("expected"),
        "trigger": task.get("trigger", True),
        "workspace_config": task.get("workspace", []),
        "grader_configs": task.get("graders", []),
        "skill_paths": skill_paths or [],
        "skill_name": skill_name,
        "skill_summary": skill_summary,
        "agent_model": task.get("agent") or os.environ.get("LLM_MODEL_NAME", "gpt-4o"),
        "agent_timeout": task.get("timeout", 300),
        "llm_base_url": os.environ.get("LLM_BASE_URL", ""),
        "llm_api_key": os.environ.get("LLM_API_KEY", ""),
        "results": [],
        "logs": [],
        "current_trial": 0,
        "total_trials": trials,
        "start_time": time.time(),
        "trial_start_time": time.time(),
        "error": None,
        "skill_tracking_enabled": True,
        "skill_tracking_reports": [],
        "debug_dir": effective_debug_dir,
    }

    # Collect all state updates from the graph
    final_state = initial_state.copy()
    async for chunk in graph.astream(initial_state, config={"recursion_limit": trials * 10}):
        # Chunk keys are node names, values are the node's return dict
        if isinstance(chunk, dict):
            for node_name, node_output in chunk.items():
                if isinstance(node_output, dict):
                    for key, value in node_output.items():
                        if key == "results":
                            # Append results, don't replace
                            if key not in final_state:
                                final_state[key] = []
                            final_state[key].extend(value)
                        elif key == "logs":
                            # Append logs, don't replace
                            if key not in final_state:
                                final_state[key] = []
                            final_state[key].extend(value)
                        elif key == "current_trial":
                            final_state[key] = value
                        else:
                            final_state[key] = value

    if not final_state:
        raise RuntimeError("Graph execution failed")

    results = final_state.get("results", [])
    all_logs = final_state.get("logs", [])

    trial_results = []
    total_duration = 0.0

    for i, result in enumerate(results):
        trial_result = TrialResult(
            task_name=task["name"],
            trial_index=i,
            reward=result.get("reward", 0.0),
            graders=[
                GraderResult(
                    grader_type=r.get("graderType", "unknown"),
                    score=r.get("score", 0.0),
                    weight=r.get("weight", 1.0),
                    details=r.get("details", ""),
                    checks=r.get("checks"),
                    reasoning=r.get("reasoning"),
                )
                for r in result.get("graders", [])
            ],
            logs=[
                LogEntry(
                    type=LogType(l.get("type", "unknown")),
                    timestamp=l.get("timestamp", 0.0),
                    data=l.get("data", {}),
                )
                for l in all_logs
                if l.get("type") not in ("setup", "cleanup", "reward")
            ],
            duration_ms=result.get("duration_ms", 0.0),
            error=result.get("error"),
            skill_tracking=result.get("skill_tracking", []),
        )
        trial_results.append(trial_result)
        total_duration += trial_result.duration_ms

    rewards = [r.reward for r in trial_results]
    pass_rate = sum(rewards) / len(rewards) if rewards else 0.0

    pass_at_k = 1 - (1 - pass_rate) ** trials
    pass_pow_k = pass_rate**trials

    return EvalReport(
        task_name=task["name"],
        pass_rate=pass_rate,
        pass_at_k=pass_at_k,
        pass_pow_k=pass_pow_k,
        trials=trial_results,
        avg_duration_ms=total_duration / len(trial_results) if trial_results else 0.0,
        timestamp=datetime.now().isoformat(),
        instruction=task.get("instruction"),
    )


async def run_quick_eval(
    instruction: str,
    graders: list[dict[str, Any]],
    workspace_files: list[dict[str, Any]] | None = None,
    skill_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Run a quick single-shot evaluation without LangGraph overhead.

    This is useful for simple evaluations that don't need trial iteration.

    Args:
        instruction: The agent instruction
        graders: List of grader configurations
        workspace_files: Optional workspace file mappings
        skill_paths: Optional skill paths to inject

    Returns:
        Evaluation result dictionary
    """
    from ..agents import DeepAgent
    from ..graders import DeterministicGrader, LLMGrader
    from ..types import GraderConfig, GraderType

    workspace = create_temp_workspace(
        [Path(w["src"]) for w in (workspace_files or [])],
        skill_paths or [],
    )

    try:
        agent = DeepAgent(
            skill_paths=skill_paths,
            enable_tracking=len(skill_paths or []) > 0,
        )
        output, tool_logs, skill_tracking_logs = await agent.run(
            instruction=instruction,
            workspace=str(workspace),
        )

        grader_results = []
        for config in graders:
            grader_type = GraderType(config.get("type", "deterministic"))

            if grader_type == GraderType.DETERMINISTIC:
                grader = DeterministicGrader()
            else:
                grader = LLMGrader()

            grader_config = GraderConfig(
                type=grader_type,
                run=config.get("run"),
                rubric=config.get("rubric"),
                weight=config.get("weight", 1.0),
            )

            logs = [{"type": "agent_result", "data": {"output": output}}]
            result = await grader.grade(workspace=workspace, config=grader_config, logs=logs)
            grader_results.append(result.to_dict())

        total_weight = sum(r.get("weight", 1.0) for r in grader_results)
        reward = (
            sum(r.get("score", 0.0) * r.get("weight", 1.0) for r in grader_results) / total_weight
        )

        # Extract skill tracking data
        skill_tracking_data = [log["data"] for log in skill_tracking_logs]

        return {
            "output": output,
            "reward": reward,
            "graders": grader_results,
            "workspace": str(workspace),
            "skill_tracking": skill_tracking_data,
        }

    finally:
        from ..providers import LocalProvider

        provider = LocalProvider()
        await provider.cleanup(workspace)
