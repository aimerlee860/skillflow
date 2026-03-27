"""Smoke command module."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from ..core.config import load_eval_config_from_path, save_report, save_summary_report

console = Console()

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
    parallel: int = 1,
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
        parallel: Number of tasks to evaluate in parallel (default: 1, sequential)

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

    if parallel <= 1 or len(config.tasks) <= 1:
        # Sequential execution (original behavior)
        for task in config.tasks:
            if not quiet:
                console.rule(f"[bold cyan]Running task: {task.name}[/bold cyan]")

            task_dict = task.to_dict()
            task_dict["trials"] = trials

            if show_progress:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[cyan]{task.description}[/cyan]"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    TimeElapsedColumn(),
                    console=console,
                ) as progress:
                    task_progress = progress.add_task(f"Task: {task.name}", total=trials)
                    report = await run_smoke_eval(
                        task_dict,
                        trials=trials,
                        skill_paths=skill_paths,
                        debug_dir=debug_dir,
                    )
                    progress.update(task_progress, completed=trials)
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
            save_report(report, output_dir, include_logs=False)
            all_reports.append(report)
            all_reports_dict.append(report.to_dict())

            if not quiet:
                _print_summary(report)
    else:
        # Parallel execution
        if not quiet:
            console.print()
            console.rule("[bold cyan]Parallel Evaluation[/bold cyan]")
            console.print(f"[dim]Tasks:[/dim] [green]{len(config.tasks)}[/green]  [dim]Concurrency:[/dim] [green]{parallel}[/green]")

        semaphore = asyncio.Semaphore(parallel)

        async def run_single_task(task) -> EvalReport:
            """Run a single task with semaphore-based concurrency control."""
            async with semaphore:
                task_dict = task.to_dict()
                task_dict["trials"] = trials

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

                return report

        # Run all tasks concurrently with semaphore
        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[cyan]Parallel evaluation[/cyan]"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                main_task = progress.add_task(
                    f"Running {len(config.tasks)} tasks (parallel={parallel})",
                    total=len(config.tasks),
                )
                tasks = [run_single_task(task) for task in config.tasks]
                for coro in asyncio.as_completed(tasks):
                    report = await coro
                    save_report(report, output_dir, include_logs=False)
                    all_reports.append(report)
                    all_reports_dict.append(report.to_dict())
                    progress.advance(main_task)
                    if not quiet:
                        _print_summary(report)
        else:
            tasks = [run_single_task(task) for task in config.tasks]
            reports = await asyncio.gather(*tasks)
            for report in reports:
                save_report(report, output_dir, include_logs=False)
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
            console.print(f"\n[dim]Summary report saved:[/dim] [cyan]{summary_path}[/cyan]")

    return all_reports_dict, output_dir


def _print_summary(report: EvalReport) -> None:
    """Print a summary of the evaluation report with rich formatting."""
    # Task header
    console.print()
    console.rule(f"[bold cyan]Task: {report.task_name}[/bold cyan]")

    # Main metrics table
    metrics_table = Table(show_header=False, box=None, padding=(0, 2))
    metrics_table.add_column("Metric", style="dim")
    metrics_table.add_column("Value", justify="right")

    pass_rate_color = "green" if report.pass_rate >= 0.7 else "yellow" if report.pass_rate >= 0.5 else "red"
    metrics_table.add_row("通过率", f"[{pass_rate_color}]{report.pass_rate:.2%}[/{pass_rate_color}]")
    metrics_table.add_row("Pass@K", f"{report.pass_at_k:.4f} [dim](至少一次成功)[/dim]")
    metrics_table.add_row("Pass^K", f"{report.pass_pow_k:.4f} [dim](全部成功)[/dim]")
    metrics_table.add_row("测试次数", str(len(report.trials)))
    metrics_table.add_row("平均耗时", f"{report.avg_duration_ms / 1000:.1f}s")

    console.print(metrics_table)

    # Trials table
    if report.trials:
        console.print("\n[bold]Trials:[/bold]")
        trials_table = Table(show_header=True, box=None, padding=(0, 1))
        trials_table.add_column("#", style="dim", width=3)
        trials_table.add_column("Status", width=6)
        trials_table.add_column("Reward", justify="right", width=8)
        trials_table.add_column("Graders")

        for i, trial in enumerate(report.trials):
            status = "[green]✓[/green]" if trial.reward >= 0.5 else "[red]✗[/red]"
            reward_color = "green" if trial.reward >= 0.5 else "red"
            reward_text = f"[{reward_color}]{trial.reward:.2%}[/{reward_color}]"

            grader_parts = []
            for grader in trial.graders:
                grader_color = "green" if grader.score >= 0.7 else "yellow" if grader.score >= 0.5 else "red"
                grader_parts.append(
                    f"[dim]{grader.grader_type}:[/dim] [{grader_color}]{grader.score:.0%}[/{grader_color}]"
                )
            graders_text = " ".join(grader_parts) if grader_parts else "[dim]-[/dim]"

            trials_table.add_row(str(i + 1), status, reward_text, graders_text)

        console.print(trials_table)

    # Skill statistics
    if report.skill_statistics:
        console.print("\n[bold]Skill Statistics:[/bold]")
        for stat in report.skill_statistics:
            skill_panel = Table(show_header=False, box=None, padding=(0, 2))
            skill_panel.add_column("Metric", style="dim")
            skill_panel.add_column("Value", justify="right")

            quality_color = "green" if stat['qualityScore'] >= 0.7 else "yellow" if stat['qualityScore'] >= 0.5 else "red"
            skill_panel.add_row(
                "[bold]质量得分[/bold]",
                f"[{quality_color}]{stat['qualityScore']:.2f}[/{quality_color}]"
            )
            if stat.get('taskCompletionScore') is not None:
                skill_panel.add_row("  └─ 任务完成", f"{stat['taskCompletionScore']:.2%} [dim](70%)[/dim]")
            if stat.get('efficiencyScore') is not None:
                skill_panel.add_row("  └─ 效率得分", f"{stat['efficiencyScore']:.2%} [dim](30%)[/dim]")

            trigger_color = "green" if stat['triggerAccuracy'] >= 0.9 else "yellow" if stat['triggerAccuracy'] >= 0.7 else "red"
            skill_panel.add_row("触发准确率", f"[{trigger_color}]{stat['triggerAccuracy']:.2%}[/{trigger_color}]")

            fp_color = "green" if stat['falsePositiveRate'] <= 0.1 else "yellow" if stat['falsePositiveRate'] <= 0.3 else "red"
            skill_panel.add_row("误触发率", f"[{fp_color}]{stat['falsePositiveRate']:.2%}[/{fp_color}]")

            if stat.get('deepUsageAccuracy') is not None:
                deep_color = "green" if stat['deepUsageAccuracy'] >= 0.5 else "yellow" if stat['deepUsageAccuracy'] >= 0.3 else "red"
                skill_panel.add_row("深度使用率", f"[{deep_color}]{stat['deepUsageAccuracy']:.2%}[/{deep_color}]")

            console.print(f"\n[bold cyan][{stat['skillName']}][/bold cyan]")
            console.print(skill_panel)
