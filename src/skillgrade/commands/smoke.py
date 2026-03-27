"""Smoke command module."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from tqdm import tqdm

from ..core.config import load_eval_config_from_path, save_report, save_summary_report
from ..core.skill_tracking import aggregate_reports
from ..core.skill_stats import calculate_skill_statistics
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
    debug_dir: str | None = None,
    skill_name: str | None = None,
    model_name: str | None = None,
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
        debug_dir: Optional directory to save grader prompts/responses for debugging
        skill_name: Optional skill name for metadata
        model_name: Optional model name for metadata

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

    all_reports: list[EvalReport] = []
    all_reports_dict: list[dict[str, Any]] = []

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
                    debug_dir=debug_dir,
                )
                pbar.update(trials)
        else:
            report = await run_smoke_eval(
                task_dict,
                trials=trials,
                skill_paths=skill_paths,
                debug_dir=debug_dir,
            )

        # Calculate skill statistics from trial results
        trial_results = [t.to_dict() for t in report.trials]
        tracking_reports = aggregate_reports(trial_results)
        if tracking_reports:
            skill_stats = calculate_skill_statistics(tracking_reports, trial_results)
            report.skill_statistics = [s.to_dict() for s in skill_stats]

        # Save individual task report (compact, no logs)
        report_path = save_report(report, output_dir, include_logs=False)
        all_reports.append(report)
        all_reports_dict.append(report.to_dict())

        if not quiet:
            _print_summary(report)

    # Generate comprehensive summary report with full agent interaction logs
    if all_reports:
        summary_path = save_summary_report(
            reports=all_reports,
            output_dir=output_dir,
            skill_name=skill_name,
            model_name=model_name,
        )
        if not quiet:
            print(f"\n汇总报告已保存: {summary_path}")

    return all_reports_dict, output_dir


def _print_summary(report: EvalReport) -> None:
    """Print a summary of the evaluation report."""
    print(f"\n任务: {report.task_name}")
    print(f"通过率:   {report.pass_rate:.2%}")
    print(f"Pass@K:   {report.pass_at_k:.4f} (至少一次成功)")
    print(f"Pass^K:   {report.pass_pow_k:.4f} (全部成功)")
    print(f"测试次数: {len(report.trials)}")
    print(f"平均耗时: {report.avg_duration_ms / 1000:.1f}s")

    for i, trial in enumerate(report.trials):
        status = "✓" if trial.reward >= 0.5 else "✗"
        print(f"  测试 {i + 1}: {status} {trial.reward:.2%}")

        for grader in trial.graders:
            print(f"    - {grader.grader_type}: {grader.score:.2%} ({grader.details})")

    # 打印技能统计信息
    if report.skill_statistics:
        print(f"\n{'─' * 40}")
        print("技能统计信息:")
        for stat in report.skill_statistics:
            print(f"\n  [{stat['skillName']}]")
            print(f"    质量得分:     {stat['qualityScore']:.2f}")
            if stat.get('taskCompletionScore') is not None:
                print(f"      ├── 任务完成: {stat['taskCompletionScore']:.2%} (权重 70%)")
            if stat.get('efficiencyScore') is not None:
                print(f"      └── 效率得分: {stat['efficiencyScore']:.2%} (权重 30%)")
            print(f"    触发准确率:   {stat['triggerAccuracy']:.2%}")
            print(f"    误触发率:     {stat['falsePositiveRate']:.2%}")
            if stat.get('deepUsageAccuracy') is not None:
                print(f"    深度使用率:   {stat['deepUsageAccuracy']:.2%}")
