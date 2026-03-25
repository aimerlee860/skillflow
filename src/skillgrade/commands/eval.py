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

    Returns:
        Tuple of (list of reports, output_dir)
    """
    from ..core import EvalRunner

    if not quiet:
        print(f"Evaluating skill: {skill_dir}")

    runner = EvalRunner(
        skill_dir=skill_dir,
        config_path=config_path,
        output_dir=output_dir,
        keep_workspaces=keep_workspaces,
    )

    try:
        temp_dir, eval_config_path = await runner.setup()

        if not quiet:
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
            quiet=quiet,
            show_progress=show_progress,
        )

        if not quiet:
            print(f"\n{'=' * 60}")
            print("Evaluation complete!")
            print(f"Results saved to: {results_dir}")
            print(f"Config saved to: {results_dir / 'eval.yaml'}")
            print(f"{'=' * 60}")

        return reports, results_dir

    finally:
        runner.cleanup()
