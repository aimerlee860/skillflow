"""CLI reporter module."""

from __future__ import annotations

from typing import Any

from ..types import EvalReport, TrialResult
from ..utils.io import fmt_score, fmt_percent, print_header, print_key_value


def print_summary(report: EvalReport) -> None:
    """Print a summary of an evaluation report.

    Args:
        report: The evaluation report to display
    """
    print()
    print("=" * 60)
    print(f"Task: {report.task_name}")
    print("=" * 60)
    print()

    print(f"Pass Rate: {fmt_score(report.pass_rate)} ({fmt_percent(report.pass_rate)})")
    print(f"Pass@K:   {fmt_score(report.pass_at_k)}")
    print(f"Pass^K:   {fmt_score(report.pass_pow_k)}")
    print(f"Trials:   {len(report.trials)}")
    print(f"Avg Time: {report.avg_duration_ms / 1000:.1f}s")
    print()

    for i, trial in enumerate(report.trials):
        status = "✓" if trial.reward >= 0.5 else "✗"
        print(f"  Trial {i + 1}: {status} {fmt_score(trial.reward)}")

        for grader in trial.graders:
            print(f"    - {grader.grader_type}: {fmt_score(grader.score)} ({grader.details})")

        if trial.error:
            print(f"    Error: {trial.error}")

    # 打印技能统计信息
    if report.skill_statistics:
        _print_skill_statistics(report.skill_statistics)

    print()


def print_reports(reports: list[dict[str, Any]]) -> None:
    """Print summaries of multiple evaluation reports.

    Args:
        reports: List of report dictionaries
    """
    print_header("SKILLGRADE RESULTS")

    # 收集所有技能统计信息用于聚合
    all_skill_stats: dict[str, list[dict]] = {}

    for report in reports:
        task_name = report.get("taskName", "unknown")
        pass_rate = report.get("passRate", 0.0)
        pass_at_k = report.get("passAtK", 0.0)
        pass_pow_k = report.get("passPowK", 0.0)
        trials = report.get("trials", [])
        avg_duration = report.get("avgDurationMs", 0.0)

        print(f"\nTask: {task_name}")
        print(f"  Pass Rate: {fmt_score(pass_rate)} ({fmt_percent(pass_rate)})")
        print(f"  Pass@K:   {fmt_score(pass_at_k)}")
        print(f"  Pass^K:   {fmt_score(pass_pow_k)}")
        print(f"  Trials:   {len(trials)}")
        print(f"  Avg Time: {avg_duration / 1000:.1f}s")

        for i, trial in enumerate(trials):
            reward = trial.get("reward", 0.0)
            status = "✓" if reward >= 0.5 else "✗"
            print(f"    Trial {i + 1}: {status} {fmt_score(reward)}")

            for grader in trial.get("graders", []):
                score = grader.get("score", 0.0)
                details = grader.get("details", "")
                gtype = grader.get("graderType", "unknown")
                print(f"      - {gtype}: {fmt_score(score)} ({details})")

        # 收集技能统计信息
        skill_stats = report.get("skillStatistics", [])
        for stat in skill_stats:
            skill_name = stat.get("skillName", "unknown")
            if skill_name not in all_skill_stats:
                all_skill_stats[skill_name] = []
            all_skill_stats[skill_name].append(stat)

    # 打印聚合后的技能统计信息
    if all_skill_stats:
        print("\n" + "=" * 60)
        print("聚合技能统计信息")
        print("=" * 60)
        _print_aggregated_skill_statistics(all_skill_stats)


def _print_skill_statistics(skill_statistics: list[dict[str, Any]]) -> None:
    """打印单个任务的技能统计信息。

    Args:
        skill_statistics: 技能统计信息列表
    """
    print()
    print("-" * 40)
    print("技能统计信息:")
    print("-" * 40)

    for stat in skill_statistics:
        skill_name = stat.get("skillName", "unknown")
        quality_score = stat.get("qualityScore", 0.0)
        trigger_accuracy = stat.get("triggerAccuracy", 0.0)
        false_positive_rate = stat.get("falsePositiveRate", 0.0)
        task_completion = stat.get("taskCompletionScore", 0.0)
        efficiency = stat.get("efficiencyScore", 0.0)
        deep_usage = stat.get("deepUsageAccuracy", 0.0)

        print(f"\n  [{skill_name}]")
        print(f"    质量得分:     {quality_score:.2f}")
        print(f"      ├── 任务完成: {fmt_percent(task_completion)} (权重 70%)")
        print(f"      └── 效率得分: {fmt_percent(efficiency)} (权重 30%)")
        print(f"    触发准确率:   {fmt_percent(trigger_accuracy)}")
        print(f"    误触发率:     {fmt_percent(false_positive_rate)}")
        print(f"    深度使用率:   {fmt_percent(deep_usage)}")


def _print_aggregated_skill_statistics(
    all_skill_stats: dict[str, list[dict]]
) -> None:
    """打印聚合后的技能统计信息。

    Args:
        all_skill_stats: 按技能名分组的统计信息
    """
    for skill_name, stats_list in all_skill_stats.items():
        # 计算平均值
        avg_quality = sum(s.get("qualityScore", 0) for s in stats_list) / len(stats_list)
        avg_trigger = sum(s.get("triggerAccuracy", 0) for s in stats_list) / len(stats_list)
        avg_false_pos = sum(s.get("falsePositiveRate", 0) for s in stats_list) / len(stats_list)
        avg_task_completion = sum(s.get("taskCompletionScore", 0) for s in stats_list) / len(stats_list)
        avg_efficiency = sum(s.get("efficiencyScore", 0) for s in stats_list) / len(stats_list)
        avg_deep_usage = sum(s.get("deepUsageAccuracy", 0) for s in stats_list) / len(stats_list)

        print(f"\n[{skill_name}]")
        print(f"  任务数量:       {len(stats_list)}")
        print(f"  平均质量得分:   {avg_quality:.2f}")
        print(f"    ├── 任务完成: {fmt_percent(avg_task_completion)}")
        print(f"    └── 效率得分: {fmt_percent(avg_efficiency)}")
        print(f"  平均触发准确率: {fmt_percent(avg_trigger)}")
        print(f"  平均误触发率:   {fmt_percent(avg_false_pos)}")
        print(f"  平均深度使用:   {fmt_percent(avg_deep_usage)}")


def print_aggregated_metrics(reports: list[dict[str, Any]]) -> None:
    """打印所有任务的聚合指标。

    Args:
        reports: 报告字典列表
    """
    if not reports:
        return

    print()
    print("=" * 60)
    print("聚合评估指标")
    print("=" * 60)

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

    if total_trials == 0:
        print("无测试数据")
        return

    # 计算指标
    overall_pass_rate = total_passes / total_trials

    # Pass@K: 至少一次成功的概率
    k = min(len(all_rewards), 5)  # 默认K=5
    if k > 0 and all_rewards:
        pass_at_k = 1 - (1 - sum(all_rewards) / len(all_rewards)) ** k
    else:
        pass_at_k = 0.0

    # Pass^K: 全部成功的概率
    if k > 0 and all_rewards:
        avg_reward = sum(all_rewards) / len(all_rewards)
        pass_pow_k = avg_reward ** k
    else:
        pass_pow_k = 0.0

    print(f"\n总体通过率:     {fmt_percent(overall_pass_rate)}")
    print(f"Pass@{k}:        {pass_at_k:.4f} (至少一次成功的概率)")
    print(f"Pass^{k}:        {pass_pow_k:.4f} (全部成功的概率)")
    print(f"总测试次数:     {total_trials}")
    print(f"总通过次数:     {total_passes}")


def validation_result(is_valid: bool, message: str) -> None:
    """Print a validation result.

    Args:
        is_valid: Whether validation passed
        message: Validation message
    """
    if is_valid:
        print(f"  \033[92m✓ {message}\033[0m")
    else:
        print(f"  \033[91m✗ {message}\033[0m")
