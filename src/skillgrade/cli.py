"""CLI module."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


def create_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser.

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog="skillgrade",
        description="Skill lifecycle management: create, evaluate, and evolve AI agent skills",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a new skill
  skillgrade init my-skill --description "Review code for bugs"

  # Evaluate a skill
  skillgrade eval ./my-skill --trials 5

  # Evolve a skill automatically
  skillgrade evolve ./my-skill --trials 5 --iterations 50

  # Preview results
  skillgrade preview --results-dir /tmp/skillgrade/my-skill
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # init command
    p_init = subparsers.add_parser("init", help="Create a new skill")
    p_init.add_argument(
        "name",
        help="Name of the skill to create",
    )
    p_init.add_argument(
        "--dir",
        "-d",
        type=Path,
        default=Path("."),
        help="Directory to create the skill in (default: current directory)",
    )
    p_init.add_argument(
        "--description",
        "-D",
        required=True,
        help="Description of what the skill does",
    )
    p_init.add_argument(
        "--template",
        "-t",
        choices=["default", "code-review", "documentation", "testing"],
        default="default",
        help="Template to use (default: default)",
    )
    p_init.add_argument(
        "--example",
        "-e",
        action="append",
        dest="examples",
        help="Add an example (can be used multiple times)",
    )
    p_init.add_argument(
        "--constraint",
        "-C",
        action="append",
        dest="constraints",
        help="Add a constraint (can be used multiple times)",
    )

    # eval command
    p_eval = subparsers.add_parser("eval", help="Run evaluation on a skill")
    p_eval.add_argument(
        "skill_dir",
        type=Path,
        help="Path to the skill directory (must contain SKILL.md)",
    )
    p_eval.add_argument(
        "--config",
        "-c",
        type=Path,
        default=None,
        dest="config_path",
        help="Path to eval.yaml configuration file",
    )
    p_eval.add_argument(
        "--trials",
        "-n",
        type=int,
        default=5,
        help="Number of trials per task (default: 5)",
    )
    p_eval.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        dest="output_dir",
        help="Output directory for results",
    )
    p_eval.add_argument(
        "--keep-workspaces",
        action="store_true",
        help="Keep workspace copies for debugging",
    )
    p_eval.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress output",
    )

    # evolve command
    p_evolve = subparsers.add_parser("evolve", help="Automatically evolve a skill")
    p_evolve.add_argument(
        "skill_dir",
        type=Path,
        help="Path to the skill directory (must contain SKILL.md)",
    )
    p_evolve.add_argument(
        "--config",
        "-c",
        type=Path,
        default=None,
        dest="config_path",
        help="Path to eval.yaml configuration file",
    )
    p_evolve.add_argument(
        "--trials",
        "-n",
        type=int,
        default=5,
        help="Number of evaluation trials per iteration (default: 5)",
    )
    p_evolve.add_argument(
        "--iterations",
        "-i",
        type=int,
        default=100,
        dest="max_iterations",
        help="Maximum number of evolution iterations (default: 100)",
    )
    p_evolve.add_argument(
        "--max-time",
        "-t",
        type=int,
        default=3600,
        dest="max_time",
        help="Maximum time in seconds (default: 3600)",
    )
    p_evolve.add_argument(
        "--patience",
        "-p",
        type=int,
        default=20,
        help="Stop after N consecutive no-improvements (default: 20)",
    )
    p_evolve.add_argument(
        "--strategy",
        "-s",
        choices=["hybrid", "autonomous", "structured"],
        default="hybrid",
        help="Evolution strategy (default: hybrid)",
    )
    p_evolve.add_argument(
        "--program",
        type=Path,
        default=None,
        dest="program_md",
        help="Path to custom program.md for evolution protocol",
    )
    p_evolve.add_argument(
        "--llm-model",
        "-m",
        default="gpt-4o",
        help="LLM model for evolution (default: gpt-4o)",
    )
    p_evolve.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Keep workspaces after completion",
    )
    p_evolve.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    # preview command
    p_preview = subparsers.add_parser("preview", help="Preview evaluation results")
    p_preview.add_argument(
        "results_dir",
        type=Path,
        nargs="?",
        default=None,
        help="Results directory (default: $TMPDIR/skillgrade)",
    )
    p_preview.add_argument(
        "--browser",
        "-b",
        action="store_true",
        help="Open in browser",
    )
    p_preview.add_argument(
        "--port",
        "-p",
        type=int,
        default=3847,
        help="Port for browser preview (default: 3847)",
    )

    return parser


def main() -> int:
    """Main CLI entry point.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = create_parser()
    args = parser.parse_args()

    if args.command == "init":
        from skillforge import SkillCreator

        creator = SkillCreator()
        skill_path = creator.create(
            skill_dir=args.dir,
            name=args.name,
            description=args.description,
            template=args.template,
            examples=args.examples or [],
            constraints=args.constraints or [],
        )
        print(f"Created skill at: {skill_path}")
        print(f"  - {skill_path / 'SKILL.md'}")
        print(f"  - {skill_path / 'eval.yaml'}")

    elif args.command == "eval":
        from .commands import run_eval

        asyncio.run(
            run_eval(
                skill_dir=args.skill_dir,
                trials=args.trials,
                config_path=args.config_path,
                output_dir=args.output_dir,
                keep_workspaces=args.keep_workspaces,
                quiet=args.quiet,
                show_progress=not args.quiet,
            )
        )

    elif args.command == "evolve":
        from skillevol.commands import run_evolve

        asyncio.run(
            run_evolve(
                skill_path=args.skill_dir,
                eval_config=args.config_path,
                trials=args.trials,
                max_iterations=args.max_iterations,
                max_time=args.max_time,
                patience=args.patience,
                strategy=args.strategy,
                program_md=args.program_md,
                llm_model=args.llm_model,
                keep_workspace=args.keep_workspace,
                verbose=args.verbose,
            )
        )

    elif args.command == "preview":
        from .commands import run_preview

        run_preview(
            results_dir=args.results_dir,
            mode="browser" if args.browser else "cli",
            port=args.port,
        )

    else:
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
