"""Eval command module - main entry point for evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from .smoke import run_smoke

console = Console()


def _print_aggregated_summary(reports: list[dict[str, Any]]) -> None:
    """打印聚合的评估指标和技能统计信息。"""
    if not reports:
        return

    # 收集所有技能统计信息
    all_skill_stats: dict[str, list[dict]] = {}

    # 计算总体指标
    total_trials = 0
    total_passes = 0
    all_rewards = []

    for report in reports:
        trials = report.get("trials", [])
        total_trials += len(trials)
        for trial in trials:
            reward = trial.get("reward", 0)
            all_rewards.append(reward)
            if reward >= 0.5:
                total_passes += 1

        # 收集技能统计信息
        skill_stats = report.get("skillStatistics", [])
        for stat in skill_stats:
            skill_name = stat.get("skillName", "unknown")
            if skill_name not in all_skill_stats:
                all_skill_stats[skill_name] = []
            all_skill_stats[skill_name].append(stat)

    if total_trials == 0:
        return

    # 计算指标
    overall_pass_rate = total_passes / total_trials

    # Pass@K: 至少一次成功的概率
    k = min(len(all_rewards), 5)
    if k > 0 and all_rewards:
        avg_reward = sum(all_rewards) / len(all_rewards)
        pass_at_k = 1 - (1 - avg_reward) ** k
        pass_pow_k = avg_reward ** k
    else:
        pass_at_k = 0.0
        pass_pow_k = 0.0

    # 打印聚合指标
    console.print()
    console.rule("[bold cyan]Aggregated Metrics[/bold cyan]")

    metrics_table = Table(show_header=False, box=None, padding=(0, 2))
    metrics_table.add_column("Metric", style="dim")
    metrics_table.add_column("Value", justify="right")

    pass_color = "green" if overall_pass_rate >= 0.7 else "yellow" if overall_pass_rate >= 0.5 else "red"
    metrics_table.add_row("总体通过率", f"[{pass_color}]{overall_pass_rate:.2%}[/{pass_color}]")
    metrics_table.add_row(f"Pass@{k}", f"{pass_at_k:.4f} [dim](至少一次成功)[/dim]")
    metrics_table.add_row(f"Pass^{k}", f"{pass_pow_k:.4f} [dim](全部成功)[/dim]")
    metrics_table.add_row("总测试次数", str(total_trials))
    metrics_table.add_row("总通过次数", str(total_passes))

    console.print(metrics_table)

    # 打印聚合后的技能统计信息
    if all_skill_stats:
        console.print()
        console.rule("[bold cyan]Aggregated Skill Statistics[/bold cyan]")

        for skill_name, stats_list in all_skill_stats.items():
            # 计算平均值
            avg_quality = sum(s.get("qualityScore", 0) for s in stats_list) / len(stats_list)
            avg_trigger = sum(s.get("triggerAccuracy", 0) for s in stats_list) / len(stats_list)
            avg_false_pos = sum(s.get("falsePositiveRate", 0) for s in stats_list) / len(stats_list)
            avg_task_completion = sum(s.get("taskCompletionScore", 0) for s in stats_list) / len(stats_list)
            avg_efficiency = sum(s.get("efficiencyScore", 0) for s in stats_list) / len(stats_list)
            avg_deep_usage = sum(s.get("deepUsageAccuracy", 0) for s in stats_list) / len(stats_list)

            skill_table = Table(show_header=False, box=None, padding=(0, 2))
            skill_table.add_column("Metric", style="dim")
            skill_table.add_column("Value", justify="right")

            skill_table.add_row("任务数量", str(len(stats_list)))

            quality_color = "green" if avg_quality >= 0.7 else "yellow" if avg_quality >= 0.5 else "red"
            skill_table.add_row("平均质量得分", f"[{quality_color}]{avg_quality:.2f}[/{quality_color}]")
            task_color = "green" if avg_task_completion >= 0.7 else "yellow" if avg_task_completion >= 0.5 else "red"
            skill_table.add_row("  └─ 任务完成", f"[{task_color}]{avg_task_completion:.2%}[/{task_color}] [dim](70%)[/dim]")
            eff_color = "green" if avg_efficiency >= 0.7 else "yellow" if avg_efficiency >= 0.5 else "red"
            skill_table.add_row("  └─ 效率得分", f"[{eff_color}]{avg_efficiency:.2%}[/{eff_color}] [dim](30%)[/dim]")

            trigger_color = "green" if avg_trigger >= 0.9 else "yellow" if avg_trigger >= 0.7 else "red"
            skill_table.add_row("平均触发准确率", f"[{trigger_color}]{avg_trigger:.2%}[/{trigger_color}]")

            fp_color = "green" if avg_false_pos <= 0.1 else "yellow" if avg_false_pos <= 0.3 else "red"
            skill_table.add_row("平均误触发率", f"[{fp_color}]{avg_false_pos:.2%}[/{fp_color}]")

            deep_color = "green" if avg_deep_usage >= 0.5 else "yellow" if avg_deep_usage >= 0.3 else "red"
            skill_table.add_row("平均深度使用率", f"[{deep_color}]{avg_deep_usage:.2%}[/{deep_color}]")

            console.print(f"\n[bold cyan][{skill_name}][/bold cyan]")
            console.print(skill_table)


def _build_json_output(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Build aggregated JSON output with stable metric semantics."""
    if not reports:
        return {"error": "No results", "pass_rate": 0.0}

    all_trials = [trial for report in reports for trial in report.get("trials", [])]
    total_trials = len(all_trials)
    total_passes = sum(1 for trial in all_trials if trial.get("reward", 0) >= 0.5)
    pass_rate = total_passes / total_trials if total_trials > 0 else 0.0
    reward = (
        sum(trial.get("reward", 0.0) for trial in all_trials) / total_trials if total_trials > 0 else 0.0
    )

    k = min(total_trials, 5)
    if k > 0:
        pass_at_k = 1 - (1 - pass_rate) ** k
        pass_pow_k = pass_rate ** k
    else:
        pass_at_k = 0.0
        pass_pow_k = 0.0

    all_skill_stats: dict[str, list[dict[str, Any]]] = {}
    for report in reports:
        for stat in report.get("skillStatistics", []):
            skill_name = stat.get("skillName", "unknown")
            all_skill_stats.setdefault(skill_name, []).append(stat)

    output: dict[str, Any] = {
        "pass_rate": pass_rate,
        "pass_at_k": pass_at_k,
        "pass_pow_k": pass_pow_k,
        "reward": reward,
        "trials": total_trials,
        "results": reports,
    }

    if all_skill_stats:
        primary_skill = next(iter(all_skill_stats.values()))
        stat_count = len(primary_skill)
        output["access_rate"] = sum(s.get("triggerAccuracy", 0.0) for s in primary_skill) / stat_count
        output["deep_usage_rate"] = sum(
            s.get("deepUsageAccuracy", s.get("deepUsageRate", 0.0)) for s in primary_skill
        ) / stat_count
        output["false_positive_rate"] = sum(s.get("falsePositiveRate", 0.0) for s in primary_skill) / stat_count
        output["effective_usage_rate"] = sum(s.get("effectiveUsageRate", 0.0) for s in primary_skill) / stat_count
        output["quality_score"] = sum(s.get("qualityScore", 0.0) for s in primary_skill) / stat_count

    return output


async def run_eval(
    skill_dir: Path,
    trials: int = 5,
    config_path: Path | None = None,
    output_dir: Path | None = None,
    keep_workspaces: bool = False,
    quiet: bool = False,
    show_progress: bool = True,
    metrics: list[str] | None = None,
    json_output: bool = False,
    parallel: int = 1,
    verbose: bool = False,
) -> tuple[list[dict[str, Any]], Path]:
    """Run evaluation on a skill.

    This command:
    1. Sets up temporary workspace in $TMPDIR/skillgrade/<skill-name>/
    2. Copies SKILL.md and generates eval.yaml in temp dir
    3. Runs smoke evaluation
    4. Saves eval.yaml and results to temp dir

    Args:
        skill_dir: Path to the skill directory (contains SKILL.md)
        trials: Number of trials per task
        config_path: Optional path to eval.yaml config file
        output_dir: Optional custom output directory
        keep_workspaces: Whether to keep workspace copies for debugging
        quiet: Suppress output
        show_progress: Show progress bars
        metrics: Optional list of metrics to focus on
        json_output: Output results as JSON to stdout
        parallel: Number of tasks to evaluate in parallel (default: 1)
        verbose: Show debug information

    Returns:
        Tuple of (list of reports, output_dir)
    """
    import json
    from ..core import EvalRunner

    if not quiet and not json_output:
        console.rule(f"[bold cyan]Skillgrade Eval[/bold cyan]")
        console.print(f"[dim]Evaluating:[/dim] [green]{skill_dir}[/green]")
        console.print()

    runner = EvalRunner(
        skill_dir=skill_dir,
        config_path=config_path,
        output_dir=output_dir,
        keep_workspaces=keep_workspaces,
    )

    try:
        temp_dir, eval_config_path = await runner.setup()

        if not quiet and not json_output:
            info_table = Table(show_header=False, box=None, padding=(0, 2))
            info_table.add_column("Key", style="dim")
            info_table.add_column("Value", style="green")
            info_table.add_row("Working directory", str(temp_dir))
            info_table.add_row("Config", str(eval_config_path))
            info_table.add_row("Results", str(runner.results_dir))
            console.print(info_table)
            console.print()

        config = runner.get_config()
        skill_paths = runner.get_skill_paths()

        # Extract skill name and model name for report metadata
        import os
        skill_name = skill_dir.name
        model_name = os.environ.get("LLM_MODEL_NAME", "gpt-4o")

        reports, results_dir = await run_smoke(
            config=config,
            temp_dir=temp_dir,
            skill_paths=skill_paths,
            trials=trials,
            output_dir=runner.results_dir,
            quiet=quiet or json_output,
            show_progress=show_progress and not json_output,
            skill_name=skill_name,
            model_name=model_name,
            parallel=parallel,
            json_output=json_output,
            verbose=verbose,
        )

        if json_output:
            print(json.dumps(_build_json_output(reports)))
        elif not quiet:
            # 打印聚合指标和技能统计信息
            _print_aggregated_summary(reports)

            console.print()
            console.rule("[bold green]✓ Evaluation Complete[/bold green]")
            console.print(f"  [dim]Results:[/dim] [cyan]{results_dir}[/cyan]")
            console.print(f"  [dim]Config:[/dim]  [cyan]{results_dir / 'eval.yaml'}[/cyan]")

        return reports, results_dir

    finally:
        runner.cleanup()
