"""Smoke command module."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from tqdm import tqdm

from ..core.config import load_eval_config_from_path, save_report
from ..graph import run_smoke_eval
from ..types import EvalConfig, EvalReport


async def run_smoke(
    config: EvalConfig,
    temp_dir: Path,
    skill_paths: list[str],
    trials: int = 5,
    output_dir: Path | None = None,
    quiet: bool = False,
    show_progress: bool = True,
) -> tuple[list[dict[str, Any]], Path]:
    """Run smoke evaluation on a skill.

    Args:
        config: Parsed eval configuration
        temp_dir: Temporary working directory
        skill_paths: List of skill paths to inject
        trials: Number of trials per task
        output_dir: Optional output directory for reports
        quiet: Suppress output
        show_progress: Show progress bars

    Returns:
        Tuple of (list of reports, output_dir)
    """
    if output_dir is None:
        output_dir = temp_dir / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save eval.yaml to results directory for reference
    from ..core.config import save_eval_config

    eval_yaml_path = temp_dir / "eval.yaml"
    if eval_yaml_path.exists():
        save_eval_config(config, output_dir / "eval.yaml")

    all_reports = []

    for task in config.tasks:
        if not quiet:
            print(f"\n{'=' * 60}")
            print(f"Running task: {task.name}")
            print(f"{'=' * 60}")

        task_dict = task.to_dict()
        task_dict["trials"] = trials

        if show_progress:
            with tqdm(total=trials, desc=task.name, unit="trial") as pbar:
                report = await run_smoke_eval(
                    task_dict,
                    trials=trials,
                    skill_paths=skill_paths,
                )
                pbar.update(trials)
        else:
            report = await run_smoke_eval(
                task_dict,
                trials=trials,
                skill_paths=skill_paths,
            )

        report_path = save_report(report, output_dir)
        all_reports.append(report.to_dict())

        if not quiet:
            _print_summary(report)

    return all_reports, output_dir


def _print_summary(report: EvalReport) -> None:
    """Print a summary of the evaluation report."""
    print(f"\nTask: {report.task_name}")
    print(f"Pass Rate: {report.pass_rate:.2%}")
    print(f"Pass@K:   {report.pass_at_k:.4f}")
    print(f"Pass^K:   {report.pass_pow_k:.4f}")
    print(f"Trials:   {len(report.trials)}")
    print(f"Avg Time: {report.avg_duration_ms / 1000:.1f}s")

    for i, trial in enumerate(report.trials):
        status = "✓" if trial.reward >= 0.5 else "✗"
        print(f"  Trial {i + 1}: {status} {trial.reward:.2%}")

        for grader in trial.graders:
            print(f"    - {grader.grader_type}: {grader.score:.2%} ({grader.details})")
