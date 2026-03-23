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

    print()


def print_reports(reports: list[dict[str, Any]]) -> None:
    """Print summaries of multiple evaluation reports.

    Args:
        reports: List of report dictionaries
    """
    print_header("SKILLGRADE RESULTS")

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
