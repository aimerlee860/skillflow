"""Graph nodes for smoke evaluation."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ..agents import OAIAgent
from ..graders import DeterministicGrader, LLMGrader
from ..providers import LocalProvider
from ..types import GraderType
from .state import SmokeState, TrialState


async def setup_node(state: SmokeState) -> dict[str, Any]:
    """Set up the workspace for evaluation.

    Args:
        state: Current graph state

    Returns:
        Updated state with workspace path
    """
    provider = LocalProvider()

    workspace = await provider.setup(
        workspace_config=state.get("workspace_config", []),
        skill_paths=state.get("skill_paths", []),
    )

    return {
        "workspace": str(workspace),
        "logs": [
            {
                "type": "setup",
                "timestamp": time.time(),
                "data": {"workspace": str(workspace)},
            }
        ],
    }


async def run_agent_node(state: SmokeState) -> dict[str, Any]:
    """Run the agent in the workspace.

    Args:
        state: Current graph state

    Returns:
        Updated state with agent output
    """
    agent = OAIAgent()
    workspace = state.get("workspace", "")

    try:
        output, tool_logs = await agent.run(
            instruction=state["instruction"],
            workspace=workspace,
        )

        return {
            "logs": [
                {
                    "type": "agent_result",
                    "timestamp": time.time(),
                    "data": {"output": output},
                }
            ]
            + [
                {
                    "type": "tool_call",
                    "timestamp": time.time(),
                    "data": log,
                }
                for log in tool_logs
            ],
        }

    except Exception as e:
        return {
            "logs": [
                {
                    "type": "agent_error",
                    "timestamp": time.time(),
                    "data": {"error": str(e)},
                }
            ],
        }


async def grade_node(state: SmokeState) -> dict[str, Any]:
    """Grade the agent's execution.

    Args:
        state: Current graph state

    Returns:
        Updated state with grader results
    """
    workspace = Path(state.get("workspace", ""))
    grader_configs = state.get("grader_configs", [])
    logs = state.get("logs", [])

    grader_results = []

    for config in grader_configs:
        grader_type = GraderType(config.get("type", "deterministic"))

        if grader_type == GraderType.DETERMINISTIC:
            grader = DeterministicGrader()
        else:
            grader = LLMGrader()

        from ..types import GraderConfig

        grader_config = GraderConfig(
            type=grader_type,
            run=config.get("run"),
            rubric=config.get("rubric"),
            weight=config.get("weight", 1.0),
            model=config.get("model"),
        )

        result = await grader.grade(workspace=workspace, config=grader_config, logs=logs)
        grader_results.append(result.to_dict())

        state["logs"].append(
            {
                "type": "grader",
                "timestamp": time.time(),
                "data": {
                    "grader_type": result.grader_type,
                    "score": result.score,
                    "details": result.details,
                },
            }
        )

    total_weight = sum(r["weight"] for r in grader_results) if grader_results else 1.0
    reward = sum(r["score"] * r["weight"] for r in grader_results) / total_weight

    return {
        "results": [
            {
                "trial_index": state.get("current_trial", 0),
                "reward": reward,
                "graders": grader_results,
                "duration_ms": 0,
            }
        ],
        "logs": [
            {
                "type": "reward",
                "timestamp": time.time(),
                "data": {"reward": reward},
            }
        ],
    }


async def cleanup_node(state: SmokeState) -> dict[str, Any]:
    """Clean up the workspace.

    Args:
        state: Current graph state

    Returns:
        Updated state
    """
    provider = LocalProvider()
    workspace = state.get("workspace", "")

    if workspace:
        await provider.cleanup(workspace)

    return {
        "current_trial": state.get("current_trial", 0) + 1,
        "logs": [
            {
                "type": "cleanup",
                "timestamp": time.time(),
                "data": {},
            }
        ],
    }


def should_continue(state: SmokeState) -> str:
    """Determine if evaluation should continue to next trial.

    Args:
        state: Current graph state

    Returns:
        "setup" to continue, "__end__" to finish
    """
    current = state.get("current_trial", 0)
    total = state.get("total_trials", 1)

    if current < total - 1:
        return "setup"
    return "__end__"


def increment_trial(state: SmokeState, updates: dict[str, Any]) -> dict[str, Any]:
    """Increment the trial counter after a complete trial.

    Args:
        state: Current graph state
        updates: Updates from the last node

    Returns:
        Updated state with incremented counter
    """
    current = state.get("current_trial", 0)
    return {"current_trial": current + 1}
