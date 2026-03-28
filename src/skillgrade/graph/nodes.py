"""Graph nodes for smoke evaluation."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ..agents import DeepAgent
from ..graders import DeterministicGrader, LLMGrader, TriggerGrader
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
        "trial_start_time": time.time(),  # 记录 trial 开始时间
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
        Updated state with agent output and skill tracking data
    """
    skill_paths = state.get("skill_paths", [])
    skill_tracking_enabled = state.get("skill_tracking_enabled", True)

    # Use DeepAgent with native skill support from deepagents framework
    agent = DeepAgent(
        model_name=state.get("agent_model"),
        base_url=state.get("llm_base_url"),
        api_key=state.get("llm_api_key"),
        skill_paths=skill_paths,
        enable_tracking=skill_tracking_enabled and len(skill_paths) > 0,
    )
    workspace = state.get("workspace", "")
    timeout = state.get("agent_timeout", 300)

    try:
        output, tool_logs, skill_tracking_logs = await agent.run(
            instruction=state["instruction"],
            workspace=workspace,
            timeout=timeout,
        )

        # Get skill tracking reports from tracker
        skill_reports = []
        if agent.get_skill_tracker():
            reports = agent.get_skill_tracker().generate_report()
            skill_reports = [r.to_dict() for r in reports]

        # 保留 agent 生成的原始日志格式
        # agent logs 已经有正确的 type 和 data 结构
        agent_logs = [
            {
                "timestamp": time.time(),
                **log,  # 保留原始 type 和 data 结构
            }
            for log in tool_logs
        ]

        return {
            "logs": agent_logs + skill_tracking_logs,
            "skill_tracking_reports": skill_reports,
        }

    except Exception as e:
        import traceback
        return {
            "logs": [
                {
                    "type": "agent_error",
                    "timestamp": time.time(),
                    "data": {"error": str(e), "traceback": traceback.format_exc()},
                }
            ],
        }


async def grade_node(state: SmokeState) -> dict[str, Any]:
    """Grade the agent's execution.

    Args:
        state: Current graph state

    Returns:
        Updated state with grader results and skill tracking
    """
    workspace = Path(state.get("workspace", ""))
    grader_configs = state.get("grader_configs", [])
    logs = state.get("logs", [])
    skill_tracking_reports = state.get("skill_tracking_reports", [])
    debug_dir = state.get("debug_dir")  # 获取调试目录

    # 为 grader 注入 task_name 和 trial_index 信息
    # 这样 LLM Grader 的 debug 日志可以正确命名
    task_name = state.get("task_name", "unknown")
    trial_index = state.get("current_trial", 0)

    # Get task and skill context from state
    instruction = state.get("instruction", "")
    expected = state.get("expected")
    trigger = state.get("trigger", True)
    skill_name = state.get("skill_name")
    skill_summary = state.get("skill_summary")

    # 在日志开头插入 agent_start 信息（如果不存在）
    if not any(log.get("type") == "agent_start" for log in logs):
        logs = [
            {
                "type": "agent_start",
                "timestamp": time.time(),
                "data": {
                    "task_name": task_name,
                    "trial_index": trial_index,
                    "instruction": instruction,
                },
            }
        ] + logs

    grader_results = []

    for config in grader_configs:
        grader_type = GraderType(config.get("type", "deterministic"))

        if grader_type == GraderType.DETERMINISTIC:
            grader = DeterministicGrader()
        elif grader_type == GraderType.TRIGGER:
            grader = TriggerGrader()
        else:
            grader = LLMGrader(debug_dir=debug_dir)

        from ..types import GraderConfig

        grader_config = GraderConfig(
            type=grader_type,
            run=config.get("run"),
            rubric=config.get("rubric"),
            weight=config.get("weight", 1.0),
            model=config.get("model"),
            expected_trigger=config.get("expected_trigger", config.get("expectedTrigger")),
        )

        # For LLM grader, pass task and skill context
        if grader_type == GraderType.LLM:
            result = await grader.grade(
                workspace=workspace,
                config=grader_config,
                logs=logs,
                # Task context from state
                instruction=instruction,
                expected=expected,
                expected_trigger=trigger,
                skill_name=skill_name,
                skill_summary=skill_summary,
            )
        else:
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

    # 计算 trial 耗时
    trial_start = state.get("trial_start_time", time.time())
    duration_ms = (time.time() - trial_start) * 1000

    # Extract skill tracking data from logs
    skill_tracking_data = [
        log["data"] for log in logs if log.get("type") == "skill_tracking"
    ]

    return {
        "results": [
            {
                "trial_index": state.get("current_trial", 0),
                "reward": reward,
                "graders": grader_results,
                "duration_ms": duration_ms,
                "skill_tracking": skill_tracking_data,
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
