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
    p_eval = subparsers.add_parser("eval", help="Evaluate a skill against test cases")
    p_eval.add_argument(
        "skill_dir",
        type=Path,
        help="Path to skill directory (must contain SKILL.md)",
    )
    p_eval.add_argument(
        "--config", "-c",
        type=Path,
        dest="config_path",
        help="Path to eval.yaml configuration",
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
        default="gpt-4o",
        help="LLM model for evolution (default: gpt-4o)",
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
    print(f"  - {skill_path / 'eval.yaml'}")
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

    # Ensure eval.yaml exists (create from template if not)
    eval_path = skill_path / "eval.yaml"
    if not eval_path.exists():
        # Read description from generated SKILL.md for eval.yaml
        skill_md_path = skill_path / "SKILL.md"
        description = args._description
        if skill_md_path.exists():
            content = skill_md_path.read_text()
            # Extract description from frontmatter if available
            import re
            match = re.search(r"^description:\s*(.+)$", content, re.MULTILINE)
            if match:
                description = match.group(1).strip()

        # Create basic eval.yaml from template
        creator = SkillCreator()
        eval_content = creator._render_eval_yaml(name=args.name, description=description)
        eval_path.write_text(eval_content)

    print(f"\n✓ Created skill at: {skill_path}")
    if (skill_path / "SKILL.md").exists():
        print(f"  - {skill_path / 'SKILL.md'}")
    print(f"  - {skill_path / 'eval.yaml'}")
    return 0


def handle_eval(args) -> int:
    """Handle eval command."""
    from skillgrade.commands import run_eval

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
    return 0


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
