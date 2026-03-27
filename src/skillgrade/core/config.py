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
    from dotenv import load_dotenv
    from pathlib import Path

    # Load from .env if exists
    project_root = Path(__file__).resolve().parent.parent.parent
    load_dotenv(project_root / ".env")

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

    # Remove unnecessary fields for saved config
    if "defaults" in config:
        config["defaults"].pop("docker", None)
        config["defaults"].pop("environment", None)
        config["defaults"].pop("provider", None)
        # Don't write agent and grader_model - read from LLM_MODEL_NAME at runtime
        config["defaults"].pop("agent", None)
        config["defaults"].pop("grader_model", None)

    # Remove grader model - read from LLM_MODEL_NAME at runtime
    for task in config.get("tasks", []):
        for grader in task.get("graders", []):
            grader.pop("model", None)

    content = yaml.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True)
    output_path.write_text(content)

    return output_path


def parse_eval_config(raw: dict[str, Any], base_dir: Path) -> EvalConfig:
    """Parse raw configuration dictionary into EvalConfig."""
    defaults = {**DEFAULT_CONFIG, **raw.get("defaults", {})}

    tasks = []
    for task_raw in raw.get("tasks", []):
        task = parse_task(task_raw, defaults, base_dir)
        tasks.append(task)

    return EvalConfig(
        version=raw.get("version", "1"),
        skill=raw.get("skill"),
        defaults=defaults,
        tasks=tasks,
    )


def parse_task(task_raw: dict[str, Any], defaults: dict[str, Any], base_dir: Path) -> TaskConfig:
    """Parse a single task configuration."""
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

    return TaskConfig(
        name=task_raw["name"],
        instruction=resolve_file_or_inline(task_raw["instruction"], base_dir),
        workspace=workspace,
        graders=graders,
        trials=task_raw.get("trials", defaults.get("trials", 5)),
        timeout=task_raw.get("timeout", defaults.get("timeout", 300)),
        agent=task_raw.get("agent", defaults.get("agent")),
        provider=task_raw.get("provider", defaults.get("provider")),
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
    - Only LLM rubric: weight = 1.0
    - LLM rubric + deterministic: LLM = 0.8, deterministic = 0.2 (split among rules)

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

    has_llm = any(g.get("type") == "llm_rubric" for g in graders)
    has_det = any(g.get("type") == "deterministic" for g in graders)
    det_count = sum(1 for g in graders if g.get("type") == "deterministic")

    if has_llm and has_det:
        # LLM + deterministic: 0.8 / 0.2
        for g in graders:
            if g.get("type") == "llm_rubric":
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
    num_positive: int = 3,
    num_negative: int = 2,
    num_evolved: int = 2,
) -> EvalConfig:
    """Generate evaluation plan using LLM.

    Args:
        skill_dir: Path to the skill directory
        model: Optional LLM model name for grading
        include_skill_md_in_rubric: Whether to include SKILL.md content in rubric.
        num_positive: Number of positive test cases
        num_negative: Number of negative test cases
        num_evolved: Number of evolved test cases

    Returns:
        EvalConfig with test cases
    """
    from .generator import EvalPlanGenerator

    generator = EvalPlanGenerator(
        model=model,
        include_skill_md_in_rubric=include_skill_md_in_rubric,
        num_positive=num_positive,
        num_negative=num_negative,
        num_evolved=num_evolved,
    )
    return generator.generate(skill_dir)
    return generator.generate(skill_dir)
