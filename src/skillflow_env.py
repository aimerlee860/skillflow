"""Unified environment variable loading for SkillFlow.

Provides a single entry point for loading LLM configuration from
multiple sources with clear priority:

1. System environment variables (highest priority)
2. .env file in current working directory
3. ~/.skillflow/env global config (lowest priority)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

console = Console()

_REQUIRED_KEYS = ["LLM_BASE_URL", "LLM_MODEL_NAME"]
_ALL_KEYS = ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL_NAME"]

_loaded = False


def _missing(keys: list[str]) -> list[str]:
    """Return keys that are not set in os.environ."""
    return [k for k in keys if not os.environ.get(k)]


def load_llm_env() -> None:
    """Load LLM environment variables with three-level priority.

    Priority order (higher wins):
      1. Existing system environment variables
      2. .env file in current working directory
      3. ~/.skillflow/env global config file

    Validation:
      - LLM_BASE_URL or LLM_MODEL_NAME missing → error and exit
      - LLM_API_KEY missing → warning (continues execution)
    """
    global _loaded
    if _loaded:
        return

    # Step 1: If all keys are already set via system env, done.
    if not _missing(_ALL_KEYS):
        _loaded = True
        return

    # Step 2: Load from ./.env (only fills missing vars)
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists() and _missing(_ALL_KEYS):
        load_dotenv(cwd_env, override=False)

    # Step 3: Load from ~/.skillflow/env global config
    if _missing(_ALL_KEYS):
        global_env = Path.home() / ".skillflow" / "env"
        if global_env.exists():
            load_dotenv(global_env, override=False)

    # Validation
    missing_required = _missing(_REQUIRED_KEYS)
    if missing_required:
        _report_missing_required(missing_required)

    if _missing(["LLM_API_KEY"]):
        _warn_missing_api_key()

    _loaded = True


def _report_missing_required(missing: list[str]) -> None:
    """Print error and exit when required env vars are missing."""
    var_list = "\n".join(f"  [cyan]{k}[/cyan]" for k in missing)
    console.print(Panel(
        f"[bold red]缺少必要环境变量:[/bold red]\n{var_list}",
        title="[bold red]SkillFlow 配置错误[/bold red]",
        border_style="red",
    ))
    console.print("\n[dim]请通过以下方式之一配置:[/dim]")
    console.print("  [green]1.[/green] 设置系统环境变量")
    console.print(f"  [green]2.[/green] 在当前目录创建 [cyan].env[/cyan] 文件")
    console.print(f"  [green]3.[/green] 在 [cyan]~/.skillflow/env[/cyan] 中配置（全局）")
    console.print()
    console.print("[dim]示例 .env 内容:[/dim]")
    console.print("  [dim]LLM_BASE_URL=https://api.openai.com/v1[/dim]")
    console.print("  [dim]LLM_API_KEY=sk-xxx[/dim]")
    console.print("  [dim]LLM_MODEL_NAME=gpt-4o[/dim]")
    sys.exit(1)


def _warn_missing_api_key() -> None:
    """Print warning when LLM_API_KEY is missing."""
    console.print(
        "[yellow]\u26a0 Warning: LLM_API_KEY 未设置，部分功能可能受限[/yellow]"
    )
