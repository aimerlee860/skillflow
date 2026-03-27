"""SkillFlow CLI - Unified interface for skill lifecycle management.

Commands:
  create  Create a new skill (template or LLM-powered)
  eval    Evaluate a skill against test cases
  evolve  Automatically evolve a skill
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


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
    project_root = Path(__file__).resolve().parent.parent
    project_env = project_root / ".env"
    if project_env.exists():
        load_dotenv(project_env)


def create_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="skillflow",
        description="Skill lifecycle management: create, test, and evolve AI agent skills",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  create    Create a new skill (LLM mode by default)
  eval      Evaluate a skill against test cases
  evolve    Automatically evolve and improve a skill

Examples:
  # Create skill with LLM (default)
  skillflow create bank-transfer --desc "处理银行转账业务"

  # Create skill from file
  skillflow create complex-skill --file ./requirements.md

  # Create skill with template mode (no LLM)
  skillflow create my-skill --desc "Review code" --no-llm

  # Evaluate a skill
  skillflow eval ./skills/bank-transfer --trials 5

  # Evolve a skill automatically
  skillflow evolve ./skills/bank-transfer --iterations 50

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

    # ========== create command ==========
    p_create = subparsers.add_parser(
        "create",
        help="Create a new skill",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # LLM mode (default, high quality)
  skillflow create my-skill --desc "Review Python code"

  # Template mode (fast, no LLM needed)
  skillflow create my-skill --desc "Review code" --no-llm

  # Long description from file
  skillflow create my-skill --file ./requirements.md

  # From existing codebase
  skillflow create project-helper --file ./README.md --from-codebase ./my-project
        """,
    )
    p_create.add_argument("name", help="Name of the skill to create")
    p_create.add_argument(
        "--desc", "-d",
        dest="description",
        help="Brief description of the skill",
    )
    p_create.add_argument(
        "--file", "-f",
        dest="description_file",
        type=Path,
        help="Read description from file (for long descriptions)",
    )
    p_create.add_argument(
        "--lang", "-L",
        choices=["auto", "zh", "en"],
        default="auto",
        help="Output language (default: auto-detect)",
    )
    p_create.add_argument(
        "--dir",
        type=Path,
        default=Path("./skills"),
        help="Output directory (default: ./skills)",
    )
    p_create.add_argument(
        "--template", "-t",
        choices=["default", "code-review", "documentation", "testing"],
        default="default",
        help="Template style (default: default)",
    )
    p_create.add_argument(
        "--example", "-e",
        action="append",
        dest="examples",
        help="Add an example (can be used multiple times)",
    )
    p_create.add_argument(
        "--constraint", "-C",
        action="append",
        dest="constraints",
        help="Add a constraint (can be used multiple times)",
    )
    # LLM mode options
    p_create.add_argument(
        "--no-llm",
        action="store_true",
        help="Use template mode instead of LLM",
    )
    p_create.add_argument(
        "--context", "-c",
        help="Additional context for LLM mode",
    )
    p_create.add_argument(
        "--from-codebase",
        type=Path,
        help="Analyze codebase to create skill (LLM mode)",
    )
    p_create.add_argument(
        "--base-url",
        help="LLM API base URL (default: LLM_BASE_URL env)",
    )
    p_create.add_argument(
        "--api-key",
        help="LLM API key (default: LLM_API_KEY env)",
    )
    p_create.add_argument(
        "--model", "-m",
        help="Model name (default: LLM_MODEL_NAME env or gpt-4o)",
    )

    # ========== eval command ==========
    p_eval = subparsers.add_parser(
        "eval",
        help="Evaluate a skill against test cases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate eval.yaml and evaluate
  skillflow eval ./skills/my-skill

  # Only generate eval.yaml (no evaluation)
  skillflow eval ./skills/my-skill --init

  # Evaluate with existing eval.yaml (skip generation)
  skillflow eval ./skills/my-skill --skip-init

  # Use specific eval.yaml file
  skillflow eval ./skills/my-skill --skip-init --config ./custom-eval.yaml

  # Generate eval.yaml to custom location
  skillflow eval ./skills/my-skill --init --target ./custom-eval.yaml
        """,
    )
    p_eval.add_argument(
        "skill_dir",
        type=Path,
        help="Path to skill directory (must contain SKILL.md)",
    )
    p_eval.add_argument(
        "--init",
        action="store_true",
        help="Only generate eval.yaml, do not evaluate",
    )
    p_eval.add_argument(
        "--skip-init",
        action="store_true",
        help="Skip eval.yaml generation, use existing file",
    )
    p_eval.add_argument(
        "--config", "-c",
        type=Path,
        dest="config_path",
        help="Path to eval.yaml to use (with --skip-init)",
    )
    p_eval.add_argument(
        "--target", "-t",
        type=Path,
        dest="target_path",
        help="Path to generate eval.yaml (only with --init)",
    )
    p_eval.add_argument(
        "--trials", "-n",
        type=int,
        default=5,
        help="Number of trials per task (default: 5)",
    )
    p_eval.add_argument(
        "--output", "-o",
        type=Path,
        dest="output_dir",
        help="Output directory for results",
    )
    p_eval.add_argument(
        "--keep-workspaces",
        action="store_true",
        help="Keep workspace copies for debugging",
    )
    p_eval.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress output",
    )
    p_eval.add_argument(
        "--base-url",
        help="LLM API base URL for eval.yaml generation",
    )
    p_eval.add_argument(
        "--api-key",
        help="LLM API key for eval.yaml generation",
    )
    p_eval.add_argument(
        "--model", "-m",
        help="Model name for eval.yaml generation (default: gpt-4o)",
    )
    p_eval.add_argument(
        "--rule-file", "-r",
        dest="rule_files",
        action="append",
        type=Path,
        help="Add a rule file for deterministic grading (can be used multiple times). "
        "When rule files are provided, weights are: LLM rubric 0.8, rules 0.2 total.",
    )
    p_eval.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON to stdout (for machine consumption)",
    )
    p_eval.add_argument(
        "--static",
        action="store_true",
        help="Run static analysis only (check SKILL.md completeness without running Agent)",
    )
    p_eval.add_argument(
        "--include-skill-md",
        action="store_true",
        help="Include full SKILL.md content in rubric prompts (default: False to reduce prompt size)",
    )

    # ========== evolve command ==========
    p_evolve = subparsers.add_parser("evolve", help="Automatically evolve a skill")
    p_evolve.add_argument(
        "skill_dir",
        type=Path,
        help="Path to skill directory (must contain SKILL.md)",
    )
    p_evolve.add_argument(
        "--config", "-c",
        type=Path,
        dest="config_path",
        help="Path to eval.yaml configuration",
    )
    p_evolve.add_argument(
        "--trials", "-n",
        type=int,
        default=5,
        help="Evaluation trials per iteration (default: 5)",
    )
    p_evolve.add_argument(
        "--iterations", "-i",
        type=int,
        default=100,
        dest="max_iterations",
        help="Maximum evolution iterations (default: 100)",
    )
    p_evolve.add_argument(
        "--max-time", "-t",
        type=int,
        default=3600,
        help="Maximum time in seconds (default: 3600)",
    )
    p_evolve.add_argument(
        "--patience", "-p",
        type=int,
        default=20,
        help="Stop after N no-improvements (default: 20)",
    )
    p_evolve.add_argument(
        "--strategy", "-s",
        choices=["hybrid", "autonomous", "structured"],
        default="hybrid",
        help="Evolution strategy (default: hybrid)",
    )
    p_evolve.add_argument(
        "--model",
        default=None,
        help="LLM model for evolution (default: LLM_MODEL_NAME env var or gpt-4o)",
    )
    p_evolve.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Keep workspaces after completion",
    )
    p_evolve.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output",
    )

    return parser


def main() -> int:
    """Main CLI entry point."""
    # Load .env file before any command processing
    _load_env_file()

    parser = create_parser()
    args = parser.parse_args()

    if args.command == "create":
        return handle_create(args)

    elif args.command == "eval":
        return handle_eval(args)

    elif args.command == "evolve":
        return handle_evolve(args)

    else:
        parser.print_help()
        return 1


def handle_create(args) -> int:
    """Handle create command."""
    # Resolve description
    description = args.description
    if args.description_file:
        if not args.description_file.exists():
            print(f"Error: Description file not found: {args.description_file}", file=sys.stderr)
            return 1
        description = args.description_file.read_text(encoding="utf-8").strip()
    elif not args.description:
        print("Error: Either --desc or --file is required.", file=sys.stderr)
        return 1

    # Store resolved description
    args._description = description

    if args.no_llm:
        # Template-based creation - use character detection
        if args.lang == "auto":
            args._lang = _detect_language(description)
        else:
            args._lang = args.lang
        return _create_from_template(args)
    else:
        # LLM-powered creation (default) - let LLM detect language itself
        args._lang = None
        return asyncio.run(_create_with_llm(args))


def _detect_language(text: str) -> str:
    """Detect language from text (simple heuristic for template mode)."""
    # Count CJK characters
    cjk_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    if cjk_count > len(text) * 0.1:
        return "zh"
    return "en"


def _create_from_template(args) -> int:
    """Create skill from template."""
    from skillforge import SkillCreator

    creator = SkillCreator(lang=args._lang)
    skill_path = creator.create(
        skill_dir=args.dir,
        name=args.name,
        description=args._description,
        template=args.template,
        examples=args.examples or [],
        constraints=args.constraints or [],
    )

    print(f"✓ Created skill at: {skill_path}")
    print(f"  - {skill_path / 'SKILL.md'}")
    return 0


async def _create_with_llm(args) -> int:
    """Create skill using LLM."""
    from skillforge import SkillCreatorAgent
    from skillforge.creator import SkillCreator

    base_url = args.base_url or os.environ.get("LLM_BASE_URL")
    api_key = args.api_key or os.environ.get("LLM_API_KEY")

    if not base_url or not api_key:
        print("Error: LLM configuration required.", file=sys.stderr)
        print("\nSet environment variables:", file=sys.stderr)
        print("  export LLM_BASE_URL=https://api.openai.com/v1", file=sys.stderr)
        print("  export LLM_API_KEY=sk-xxx", file=sys.stderr)
        print("\nOr use --base-url and --api-key options.", file=sys.stderr)
        return 1

    agent = SkillCreatorAgent(
        base_url=base_url,
        api_key=api_key,
        model_name=args.model,
    )

    if args.from_codebase:
        print(f"Analyzing codebase at {args.from_codebase}...")
        skill_path = await agent.analyze_codebase_for_skill(
            codebase_path=args.from_codebase,
            skill_name=args.name,
            output_dir=args.dir,
        )
    else:
        print(f"Creating skill '{args.name}' with LLM...")
        skill_path = await agent.create_skill(
            name=args.name,
            description=args._description,
            output_dir=args.dir,
            context=args.context,
            examples=args.examples,
            template=args.template,
        )

    print(f"\n✓ Created skill at: {skill_path}")
    if (skill_path / "SKILL.md").exists():
        print(f"  - {skill_path / 'SKILL.md'}")
    return 0


def handle_eval(args) -> int:
    """Handle eval command."""
    from skillgrade.commands import run_eval
    skill_dir: Path = args.skill_dir
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        print(f"Error: SKILL.md not found in {skill_dir}", file=sys.stderr)
        return 1

    # Handle --static (static analysis only)
    if getattr(args, 'static', False):
        return _run_static_analysis(skill_dir, json_output=getattr(args, 'json', False))

    # Determine eval.yaml path
    if args.init and args.target_path:
        eval_path = args.target_path
    elif args.config_path:
        eval_path = args.config_path
    else:
        eval_path = skill_dir / "eval.yaml"

    # Handle --init (only generate eval.yaml)
    if args.init:
        _generate_eval_yaml(skill_md, eval_path, args)
        print(f"✓ Generated eval.yaml at: {eval_path}")
        return 0

    # Handle --skip-init or normal mode
    if args.skip_init:
        # Use specified or default eval.yaml without generating
        if args.config_path:
            eval_path = args.config_path
        # else: use skill_dir/eval.yaml
    else:
        # Default: generate eval.yaml before evaluation
        _generate_eval_yaml(skill_md, eval_path, args)

    # Run evaluation
    asyncio.run(
        run_eval(
            skill_dir=args.skill_dir,
            trials=args.trials,
            config_path=eval_path,
            output_dir=args.output_dir,
            keep_workspaces=args.keep_workspaces,
            quiet=args.quiet,
            show_progress=not args.quiet,
            json_output=getattr(args, 'json', False),
        )
    )
    return 0


def _run_static_analysis(skill_dir: Path, json_output: bool = False) -> int:
    """Run static analysis on a skill directory.

    Args:
        skill_dir: Path to the skill directory
        json_output: Whether to output as JSON

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    from skillgrade.core.static_analyzer import run_static_analysis, format_static_report
    import json

    report = run_static_analysis(skill_dir)

    if json_output:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(format_static_report(report))

    # Return non-zero if there are errors
    return 0 if len(report.errors) == 0 else 1


def _generate_eval_yaml(skill_md: Path, eval_path: Path, args) -> None:
    """Generate eval.yaml from skill analysis."""
    from skillgrade.core.config import save_eval_config
    from skillgrade.core.generator import generate_eval_plan

    skill_dir = skill_md.parent
    include_skill_md = getattr(args, "include_skill_md", False)

    print(f"Analyzing skill at {skill_dir}...")
    config = generate_eval_plan(
        skill_dir,
        include_skill_md_in_rubric=include_skill_md,
    )
    save_eval_config(config, eval_path)
    print(f"  Generated {len(config.tasks)} test tasks based on skill analysis")


def handle_evolve(args) -> int:
    """Handle evolve command."""
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
            llm_model=args.model,
            keep_workspace=args.keep_workspace,
            verbose=args.verbose,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
