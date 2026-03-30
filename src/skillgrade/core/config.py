"""Core configuration module."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from ..types import (
    EvalConfig,
    EvalReport,
    GraderConfig,
    GraderType,
    SkillInfo,
    TaskConfig,
    TrialResult,
    WorkspaceFile,
)


DEFAULT_CONFIG = {
    "trials": 5,
    "timeout": 300,
    "threshold": 0.8,
}


def _get_current_model_name() -> str:
    """Get the current LLM model name from environment or .env file."""
    import os
    from skillflow_env import load_llm_env

    load_llm_env()

    return os.environ.get("LLM_MODEL_NAME", "gpt-4o")


def load_eval_config(skill_dir: Path) -> EvalConfig:
    """Load and parse eval.yaml from skill directory."""
    config_path = skill_dir / "eval.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"eval.yaml not found in {skill_dir}")

    content = config_path.read_text()
    raw = yaml.safe_load(content)

    return parse_eval_config(raw, skill_dir)


def load_eval_config_from_path(config_path: Path, base_dir: Path | None = None) -> EvalConfig:
    """Load and parse eval.yaml from a specific path.

    Args:
        config_path: Path to the eval.yaml file
        base_dir: Base directory for resolving file references (defaults to config_path's parent)

    Returns:
        Parsed EvalConfig

    Raises:
        FileNotFoundError: If config file doesn't exist
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    if base_dir is None:
        base_dir = config_path.parent

    content = config_path.read_text()
    raw = yaml.safe_load(content)

    return parse_eval_config(raw, base_dir)


def save_eval_config(config: EvalConfig | dict[str, Any], output_path: Path) -> Path:
    """Save eval configuration to a YAML file.

    Args:
        config: EvalConfig object or raw dict
        output_path: Path to save the config

    Returns:
        Path to the saved file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if hasattr(config, "to_dict"):
        config = config.to_dict()

    # Clean up settings - remove runtime fields
    if "settings" in config:
        for runtime_field in ["docker", "environment", "provider", "agent", "grader_model"]:
            config["settings"].pop(runtime_field, None)

    # Clean up tasks
    for task in config.get("tasks", []):
        # Keep workspace field but ensure it's a list
        if "workspace" not in task:
            task["workspace"] = []

        for grader in task.get("graders", []):
            grader.pop("model", None)
            # Remove null fields
            keys_to_remove = [k for k, v in grader.items() if v is None]
            for k in keys_to_remove:
                del grader[k]

        # Remove null fields from task (except workspace)
        keys_to_remove = [k for k, v in task.items() if v is None and k != "workspace"]
        for k in keys_to_remove:
            del task[k]

    content = yaml.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True)
    output_path.write_text(content)

    return output_path


def parse_eval_config(raw: dict[str, Any], base_dir: Path) -> EvalConfig:
    """Parse raw configuration dictionary into EvalConfig.

    Supports both new format (skill object, settings) and legacy format
    (skill string, defaults, version).
    """
    # Parse skill info (support both new and legacy formats)
    skill_info = None
    skill_raw = raw.get("skill")
    if skill_raw:
        if isinstance(skill_raw, dict):
            # New format: skill is an object with name and summary
            skill_info = SkillInfo(
                name=skill_raw.get("name", ""),
                summary=skill_raw.get("summary"),
            )
        else:
            # Legacy format: skill is a string
            skill_info = SkillInfo(name=str(skill_raw))

    # Parse settings (support both new 'settings' and legacy 'defaults')
    settings = {**DEFAULT_CONFIG, **raw.get("settings", raw.get("defaults", {}))}

    tasks = []
    for task_raw in raw.get("tasks", []):
        task = parse_task(task_raw, settings, base_dir)
        tasks.append(task)

    return EvalConfig(
        skill=skill_info,
        settings=settings,
        tasks=tasks,
    )


def parse_task(task_raw: dict[str, Any], defaults: dict[str, Any], base_dir: Path) -> TaskConfig:
    """Parse a single task configuration.

    Supports both new format (trigger, expected) and legacy format (expected_trigger).
    """
    workspace = []
    for ws_raw in task_raw.get("workspace", []):
        ws = WorkspaceFile(
            src=str(base_dir / ws_raw["src"]),
            dest=ws_raw["dest"],
            chmod=ws_raw.get("chmod"),
        )
        workspace.append(ws)

    graders = []
    for grader_raw in task_raw.get("graders", []):
        grader = parse_grader(grader_raw, defaults, base_dir)
        graders.append(grader)

    # Support both new 'trigger' and legacy 'expected_trigger' fields
    trigger = task_raw.get("trigger", task_raw.get("expected_trigger", True))

    # Parse expected field
    expected = task_raw.get("expected")
    if expected:
        expected = resolve_file_or_inline(expected, base_dir)

    return TaskConfig(
        name=task_raw["name"],
        instruction=resolve_file_or_inline(task_raw["instruction"], base_dir),
        expected=expected,
        trigger=trigger,
        workspace=workspace,
        graders=graders,
        trials=task_raw.get("trials", defaults.get("trials", 5)),
        timeout=task_raw.get("timeout", defaults.get("timeout", 300)),
    )


def parse_grader(
    grader_raw: dict[str, Any], defaults: dict[str, Any], base_dir: Path
) -> GraderConfig:
    """Parse a grader configuration."""
    grader_type = GraderType(grader_raw["type"])

    run_content = None
    if grader_raw.get("run"):
        run_content = resolve_file_or_inline(grader_raw["run"], base_dir)

    rubric_content = None
    if grader_raw.get("rubric"):
        rubric_content = resolve_file_or_inline(grader_raw["rubric"], base_dir)

    return GraderConfig(
        type=grader_type,
        run=run_content,
        rubric=rubric_content,
        weight=grader_raw.get("weight", 1.0),
        model=grader_raw.get("model", defaults.get("grader_model")),
        setup=grader_raw.get("setup"),
        expected_trigger=grader_raw.get("expectedTrigger", grader_raw.get("expected_trigger")),
    )


def resolve_file_or_inline(value: str, base_dir: Path) -> str:
    """Resolve a value that may be a file path or inline content."""
    stripped = value.strip()

    if _looks_like_file_path(stripped) and (base_dir / stripped).exists():
        return (base_dir / stripped).read_text()

    return value


def _looks_like_file_path(value: str) -> bool:
    """Check if a value looks like a file path rather than content."""
    if "\n" in value:
        return False
    if value.startswith("#") or value.startswith("-"):
        return False
    if re.match(r"^[a-zA-Z0-9_\-./]+$", value):
        return True
    return False


def normalize_grader_weights(graders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize grader weights based on grader types.

    Rules:
    - Only LLM: weight = 1.0
    - LLM + deterministic: LLM = 0.8, deterministic = 0.2 (split among rules)

    Args:
        graders: List of grader configurations

    Returns:
        Graders with normalized weights
    """
    if not graders:
        return graders

    # Check if all graders already have explicit weights
    has_explicit_weights = all(g.get("weight") is not None for g in graders)
    if has_explicit_weights:
        return graders

    has_llm = any(g.get("type") == "llm" for g in graders)
    has_det = any(g.get("type") == "deterministic" for g in graders)
    det_count = sum(1 for g in graders if g.get("type") == "deterministic")

    if has_llm and has_det:
        # LLM + deterministic: 0.8 / 0.2
        for g in graders:
            if g.get("type") == "llm":
                g["weight"] = 0.8
            else:
                g["weight"] = round(0.2 / det_count, 2)
    elif has_llm:
        # Only LLM: weight 1.0
        for g in graders:
            g["weight"] = 1.0 / len(graders)
    elif has_det:
        # Only deterministic: split evenly
        for g in graders:
            g["weight"] = 1.0 / det_count

    return graders


def save_report(report: EvalReport, output_dir: Path, include_logs: bool = False) -> Path:
    """Save an evaluation report to JSON file.

    Args:
        report: The evaluation report to save
        output_dir: Directory to save the report
        include_logs: Whether to include detailed agent interaction logs

    Returns:
        Path to the saved file
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    import orjson

    timestamp = report.timestamp.replace(":", "-").replace(".", "-")
    filename = f"{report.task_name}_{timestamp}.json"
    filepath = output_dir / filename

    with open(filepath, "wb") as f:
        f.write(orjson.dumps(report.to_dict(include_logs=include_logs), option=orjson.OPT_INDENT_2))

    return filepath


def save_summary_report(
    reports: list[EvalReport],
    output_dir: Path,
    skill_name: str | None = None,
    model_name: str | None = None,
) -> Path:
    """Save a comprehensive summary report combining all task results.

    This generates evaluation_report.json with:
    - Metadata (skill name, timestamp, model, trials)
    - Aggregate metrics across all tasks
    - Aggregate skill statistics
    - Detailed task reports with full agent interaction logs

    Args:
        reports: List of evaluation reports (one per task)
        output_dir: Directory to save the report
        skill_name: Optional skill name for metadata
        model_name: Optional model name for metadata

    Returns:
        Path to the saved summary file
    """
    from datetime import datetime
    import orjson

    output_dir.mkdir(parents=True, exist_ok=True)

    # Calculate aggregate metrics
    total_trials = sum(len(r.trials) for r in reports)
    total_passes = sum(
        sum(1 for t in r.trials if t.reward >= 0.5)
        for r in reports
    )
    overall_pass_rate = total_passes / total_trials if total_trials > 0 else 0.0

    # Calculate pass@k and pass^k
    k = min(total_trials, 5)
    if k > 0:
        pass_at_k = 1 - (1 - overall_pass_rate) ** k
        pass_pow_k = overall_pass_rate ** k
    else:
        pass_at_k = 0.0
        pass_pow_k = 0.0

    # Aggregate skill statistics
    all_skill_stats: dict[str, list[dict]] = {}
    for report in reports:
        for stat in report.skill_statistics:
            skill = stat.get("skillName", "unknown")
            if skill not in all_skill_stats:
                all_skill_stats[skill] = []
            all_skill_stats[skill].append(stat)

    aggregated_skill_stats = []
    for skill_name_key, stats_list in all_skill_stats.items():
        avg_stat = {
            "skillName": skill_name_key,
            "taskCount": len(stats_list),
            "avgQualityScore": sum(s.get("qualityScore", 0) for s in stats_list) / len(stats_list),
            "avgTriggerAccuracy": sum(s.get("triggerAccuracy", 0) for s in stats_list) / len(stats_list),
            "avgFalsePositiveRate": sum(s.get("falsePositiveRate", 0) for s in stats_list) / len(stats_list),
            "avgTaskCompletionScore": sum(s.get("taskCompletionScore", 0) for s in stats_list) / len(stats_list),
            "avgEfficiencyScore": sum(s.get("efficiencyScore", 0) for s in stats_list) / len(stats_list),
            "avgDeepUsageAccuracy": sum(s.get("deepUsageAccuracy", 0) for s in stats_list) / len(stats_list),
        }
        aggregated_skill_stats.append(avg_stat)

    # Build summary report
    summary = {
        "metadata": {
            "skillName": skill_name,
            "evaluatedAt": datetime.now().isoformat(),
            "model": model_name,
            "totalTrialsPerTask": reports[0].trials.__len__() if reports else 0,
        },
        "aggregateMetrics": {
            "overallPassRate": overall_pass_rate,
            "passAtK": pass_at_k,
            "passPowK": pass_pow_k,
            "totalTasks": len(reports),
            "totalTrialCount": total_trials,
            "totalPassCount": total_passes,
        },
        "aggregateSkillStatistics": aggregated_skill_stats,
        "tasks": [
            {
                **report.to_dict(include_logs=True),  # Include full agent interaction logs
            }
            for report in reports
        ],
    }

    # Save to fixed filename for easy programmatic access
    filepath = output_dir / "evaluation_report.json"
    with open(filepath, "wb") as f:
        f.write(orjson.dumps(summary, option=orjson.OPT_INDENT_2))

    return filepath


def generate_eval_plan(
    skill_dir: Path,
    model: str | None = None,
    include_skill_md_in_rubric: bool = False,
    parallel: int = 4,
    # Removed fixed count parameters - now uses smart planning
) -> EvalConfig:
    """Generate evaluation plan using intelligent test planning.

    Analyzes skill complexity and automatically determines appropriate
    number and distribution of test cases.

    Args:
        skill_dir: Path to the skill directory
        model: Optional LLM model name for grading
        include_skill_md_in_rubric: Whether to include SKILL.md content in rubric.
        parallel: Number of parallel threads for generation (default: 4)

    Returns:
        EvalConfig with intelligently planned test cases
    """
    from .generator import generate_eval_plan as smart_generate

    return smart_generate(
        skill_dir=skill_dir,
        model=model,
        include_skill_md_in_rubric=include_skill_md_in_rubric,
        parallel=parallel,
    )
