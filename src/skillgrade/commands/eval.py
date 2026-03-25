"""Eval command module - main entry point for evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .smoke import run_smoke


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
) -> tuple[list[dict[str, Any]], Path]:
    """Run evaluation on a skill.

    This command:
    1. Sets up temporary workspace in $TMPDIR/skillgrade/<skill-name>/
    2. Copies SKILL.md and generates eval.yaml to temp dir
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

    Returns:
        Tuple of (list of reports, output_dir)
    """
    import json
    from ..core import EvalRunner

    if not quiet and not json_output:
        print(f"Evaluating skill: {skill_dir}")

    runner = EvalRunner(
        skill_dir=skill_dir,
        config_path=config_path,
        output_dir=output_dir,
        keep_workspaces=keep_workspaces,
    )

    try:
        temp_dir, eval_config_path = await runner.setup()

        if not quiet and not json_output:
            print(f"Working directory: {temp_dir}")
            print(f"Config: {eval_config_path}")
            print(f"Results: {runner.results_dir}")
            print()

        config = runner.get_config()
        skill_paths = runner.get_skill_paths()

        reports, results_dir = await run_smoke(
            config=config,
            temp_dir=temp_dir,
            skill_paths=skill_paths,
            trials=trials,
            output_dir=runner.results_dir,
            quiet=quiet or json_output,
            show_progress=show_progress and not json_output,
        )

        if json_output:
            # Output aggregated results as JSON to stdout
            if reports:
                # Aggregate metrics across all tasks
                total_trials = sum(r.get("trials", 0) for r in reports)
                total_passes = sum(
                    sum(1 for t in r.get("trials", []) if t.get("reward", 0) >= 0.5)
                    for r in reports
                )
                pass_rate = total_passes / total_trials if total_trials > 0 else 0.0

                # Calculate pass@k
                import math
                pass_at_k = 1 - math.prod(1 - t.get("reward", 0) for t in reports[0].get("trials", [])) if reports else 0.0

                # Get skill statistics if available
                skill_stats = reports[0].get("skillStatistics", [{}]) if reports else [{}]

                output = {
                    "pass_rate": pass_rate,
                    "pass_at_k": pass_at_k,
                    "pass_pow_k": pass_rate,  # Simplified
                    "reward": sum(r.get("avgReward", r.get("avg_reward", 0)) for r in reports) / len(reports) if reports else 0.0,
                    "trials": total_trials,
                    "results": reports,
                }

                # Add skill metrics if available
                if skill_stats:
                    stat = skill_stats[0] if skill_stats else {}
                    output["access_rate"] = stat.get("triggerAccuracy", 1.0)
                    output["deep_usage_rate"] = stat.get("deepUsageRate", 0.0)
                    output["false_positive_rate"] = stat.get("falsePositiveRate", 0.0)
                    output["effective_usage_rate"] = stat.get("effectiveUsageRate", 0.0)
                    output["quality_score"] = stat.get("qualityScore", 0.0)

                print(json.dumps(output))
            else:
                print(json.dumps({"error": "No results", "pass_rate": 0.0}))
        elif not quiet:
            print(f"\n{'=' * 60}")
            print("Evaluation complete!")
            print(f"Results saved to: {results_dir}")
            print(f"Config saved to: {results_dir / 'eval.yaml'}")
            print(f"{'=' * 60}")

        return reports, results_dir

    finally:
        runner.cleanup()
