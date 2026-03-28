"""CLI module."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

console = Console()


def _load_env_file() -> None:
    """Load .env file from multiple locations.

    Search order:
    1. Current working directory (./env)
    2. Project root (relative to this file's location)
    """
    # Try current working directory first
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        load_dotenv(cwd_env)
        return

    # Try project root (where pyproject.toml is)
    project_root = Path(__file__).resolve().parent.parent.parent
    project_env = project_root / ".env"
    if project_env.exists():
        load_dotenv(project_env)


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
Commands:
  init      Create skill from template (fast, no LLM needed)
  create    Create skill using LLM (high quality, needs API key)
  improve   Improve existing skill with LLM feedback
  eval      Evaluate a skill against test cases
  evolve    Automatically evolve a skill
  preview   Preview evaluation results

Examples:
  # Quick skill creation (template-based)
  skillgrade init my-skill --description "Review code for bugs"

  # LLM-powered skill creation
  skillgrade create python-linter \\
    --description "Lint Python code for style and errors" \\
    --example "Check PEP 8 compliance"

  # Improve existing skill
  skillgrade improve ./my-skill --feedback "Add more error examples"

  # Evaluate a skill
  skillgrade eval ./my-skill --trials 5

  # Evolve a skill automatically
  skillgrade evolve ./my-skill --trials 5 --iterations 50

Environment Variables:
  LLM_BASE_URL    API endpoint (e.g., https://api.openai.com/v1)
  LLM_API_KEY     API key for authentication
  LLM_MODEL_NAME  Model to use (default: gpt-4o)

Configuration:
  Environment variables can be set via .env file in:
  - Current working directory
  - Project root directory
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # init command
    p_init = subparsers.add_parser("init", help="Create a new skill (template-based)")
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
    p_init.add_argument(
        "--rule-file",
        "-r",
        dest="rule_files",
        action="append",
        type=Path,
        help="Add a rule file for deterministic grading (can be used multiple times). "
        "Weights: LLM rubric 0.8, rules 0.2 total.",
    )

    # create command (LLM-powered)
    p_create = subparsers.add_parser(
        "create",
        help="Create a skill using LLM (skill-creator powered)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic creation
  skillgrade create python-linter --description "Lint Python code"

  # With examples and context
  skillgrade create api-tester \\
    --description "Test REST APIs" \\
    --example "Test GET /users endpoint" \\
    --context "Our API uses OAuth2 authentication"

  # From existing codebase
  skillgrade create project-helper \\
    --from-codebase ./my-project \\
    --description "Help with this project"

  # With custom LLM settings
  skillgrade create my-skill \\
    --description "..." \\
    --base-url https://api.openai.com/v1 \\
    --model gpt-4o
        """,
    )
    p_create.add_argument(
        "name",
        help="Name of the skill to create",
    )
    p_create.add_argument(
        "--description",
        "-D",
        required=True,
        help="Description of what the skill does",
    )
    p_create.add_argument(
        "--dir",
        "-d",
        type=Path,
        default=Path("."),
        help="Directory to create the skill in (default: current directory)",
    )
    p_create.add_argument(
        "--example",
        "-e",
        action="append",
        dest="examples",
        help="Add an example use case (can be used multiple times)",
    )
    p_create.add_argument(
        "--context",
        "-c",
        type=str,
        default=None,
        help="Additional context (code snippets, docs, requirements)",
    )
    p_create.add_argument(
        "--template",
        "-t",
        choices=["default", "code-review", "documentation", "testing"],
        default="default",
        help="Template style to follow (default: default)",
    )
    p_create.add_argument(
        "--from-codebase",
        type=Path,
        default=None,
        help="Analyze existing codebase to create skill",
    )
    # LLM configuration
    p_create.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="LLM API base URL (default: LLM_BASE_URL env var)",
    )
    p_create.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="LLM API key (default: LLM_API_KEY env var)",
    )
    p_create.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="Model name (default: LLM_MODEL_NAME env var or gpt-4o)",
    )
    p_create.add_argument(
        "--max-iterations",
        type=int,
        default=50,
        help="Max agent iterations (default: 50)",
    )

    # improve command (LLM-powered)
    p_improve = subparsers.add_parser(
        "improve",
        help="Improve an existing skill using LLM",
    )
    p_improve.add_argument(
        "skill_dir",
        type=Path,
        help="Path to the skill directory to improve",
    )
    p_improve.add_argument(
        "--feedback",
        "-f",
        required=True,
        help="Feedback on what to improve",
    )
    p_improve.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="LLM API base URL",
    )
    p_improve.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="LLM API key",
    )
    p_improve.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="Model name",
    )

    # eval command
    p_eval = subparsers.add_parser("eval", help="Run evaluation on a skill")
    p_eval.add_argument(
        "skill_dir",
        type=Path,
        nargs="?",
        default=None,
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
    p_eval.add_argument(
        "--metric",
        "-m",
        type=str,
        default=None,
        dest="metrics",
        help="Comma-separated metrics to focus on (e.g., 'pass_rate,access_rate'). "
        "Run 'skillgrade metrics' to see all available metrics.",
    )
    p_eval.add_argument(
        "--list-metrics",
        action="store_true",
        help="List all available metrics and exit",
    )
    p_eval.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON to stdout (for machine consumption)",
    )
    p_eval.add_argument(
        "--parallel",
        "-j",
        type=int,
        default=1,
        dest="parallel",
        help="Number of tasks to evaluate in parallel (default: 1, sequential)",
    )
    # deep-analysis removed - always use deep analysis now

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
        default=None,
        help="LLM model for evolution (default: LLM_MODEL_NAME env var or gpt-4o)",
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
    p_evolve.add_argument(
        "--parallel",
        "-j",
        type=int,
        default=1,
        dest="parallel",
        help="Number of tasks to evaluate in parallel (default: 1, sequential)",
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
    # Load .env file before any command processing
    _load_env_file()

    parser = create_parser()
    args = parser.parse_args()

    if args.command == "init":
        from skillforge import SkillCreator
        from .core.eval_config import EvalConfigGenerator

        creator = SkillCreator()
        skill_path = creator.create(
            skill_dir=args.dir,
            name=args.name,
            description=args.description,
            template=args.template,
            examples=args.examples or [],
            constraints=args.constraints or [],
        )

        # Generate eval.yaml
        rule_contents = None
        if args.rule_files:
            rule_contents = []
            for rule_path in args.rule_files:
                if rule_path.exists():
                    rule_contents.append(rule_path.read_text())
                else:
                    console.print(f"[yellow]Warning: Rule file not found: {rule_path}[/yellow]")

        eval_generator = EvalConfigGenerator()
        eval_path = skill_path / "eval.yaml"
        eval_generator.generate_to_file(
            name=args.name,
            description=args.description,
            output_path=eval_path,
            rule_files=rule_contents,
        )

        console.print(f"[bold green]✓ Skill Created[/bold green]")
        console.print(f"  [dim]Location:[/dim] [cyan]{skill_path}[/cyan]")
        console.print(f"  [dim]SKILL.md:[/dim]  [cyan]{skill_path / 'SKILL.md'}[/cyan]")
        console.print(f"  [dim]eval.yaml:[/dim] [cyan]{eval_path}[/cyan]")

    elif args.command == "create":
        from skillforge import SkillCreatorAgent

        # Validate LLM config
        base_url = args.base_url or os.environ.get("LLM_BASE_URL")
        api_key = args.api_key or os.environ.get("LLM_API_KEY")

        if not base_url or not api_key:
            console.print("[red]Error: LLM configuration required.[/red]")
            console.print("\n[dim]Set environment variables:[/dim]")
            console.print("  [cyan]export LLM_BASE_URL=https://api.openai.com/v1[/cyan]")
            console.print("  [cyan]export LLM_API_KEY=sk-xxx[/cyan]")
            console.print("\n[dim]Or use --base-url and --api-key options.[/dim]")
            return 1

        agent = SkillCreatorAgent(
            base_url=base_url,
            api_key=api_key,
            model_name=args.model,
            max_iterations=args.max_iterations,
        )

        if args.from_codebase:
            # Create from codebase analysis
            console.print(f"[dim]Analyzing codebase at[/dim] [cyan]{args.from_codebase}[/cyan][dim]...[/dim]")

            async def run_create():
                return await agent.analyze_codebase_for_skill(
                    codebase_path=args.from_codebase,
                    skill_name=args.name,
                    output_dir=args.dir,
                )

            skill_path = asyncio.run(run_create())
        else:
            # Create from description
            console.print(f"[dim]Creating skill[/dim] [green]{args.name}[/green] [dim]using LLM...[/dim]")

            async def run_create():
                return await agent.create_skill(
                    name=args.name,
                    description=args.description,
                    output_dir=args.dir,
                    context=args.context,
                    examples=args.examples,
                    template=args.template,
                )

            skill_path = asyncio.run(run_create())

        console.print(f"\n[bold green]✓ Skill Created[/bold green]")
        console.print(f"  [dim]Location:[/dim] [cyan]{skill_path}[/cyan]")
        if (skill_path / "SKILL.md").exists():
            console.print(f"  [dim]SKILL.md:[/dim]  [cyan]{skill_path / 'SKILL.md'}[/cyan]")
        if (skill_path / "eval.yaml").exists():
            console.print(f"  [dim]eval.yaml:[/dim] [cyan]{skill_path / 'eval.yaml'}[/cyan]")

    elif args.command == "improve":
        from skillforge import SkillCreatorAgent

        base_url = args.base_url or os.environ.get("LLM_BASE_URL")
        api_key = args.api_key or os.environ.get("LLM_API_KEY")

        if not base_url or not api_key:
            console.print("[red]Error: LLM configuration required.[/red]")
            return 1

        agent = SkillCreatorAgent(
            base_url=base_url,
            api_key=api_key,
            model_name=args.model,
        )

        console.print(f"[dim]Improving skill at[/dim] [cyan]{args.skill_dir}[/cyan][dim]...[/dim]")

        async def run_improve():
            return await agent.improve_skill(
                skill_path=args.skill_dir,
                feedback=args.feedback,
            )

        skill_path = asyncio.run(run_improve())
        console.print(f"[bold green]✓ Skill improved at[/bold green] [cyan]{skill_path}[/cyan]")

    elif args.command == "eval":
        from .commands import run_eval
        from .core.metrics import get_available_metrics_info, parse_metrics_list

        # Handle --list-metrics
        if args.list_metrics:
            print(get_available_metrics_info())
            return 0

        # Validate skill_dir is provided for actual evaluation
        if args.skill_dir is None:
            console.print("[red]Error: skill_dir is required for evaluation[/red]")
            console.print("[dim]Use --list-metrics to see available metrics[/dim]")
            return 1

        # Parse metrics if provided
        metrics = None
        if args.metrics:
            metrics = parse_metrics_list(args.metrics)

        asyncio.run(
            run_eval(
                skill_dir=args.skill_dir,
                trials=args.trials,
                config_path=args.config_path,
                output_dir=args.output_dir,
                keep_workspaces=args.keep_workspaces,
                quiet=args.quiet,
                show_progress=not args.quiet,
                metrics=metrics,
                json_output=getattr(args, 'json', False),
                parallel=args.parallel,
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
                parallel=args.parallel,
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
