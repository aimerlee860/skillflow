"""Prompt management system - centralized loading, rendering and logging."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()

# Templates directory
_TEMPLATES_DIR = Path(__file__).parent


@dataclass
class PromptLog:
    """Record of a single prompt rendering."""

    name: str
    template: str
    variables: dict[str, Any]
    rendered: str


class PromptManager:
    """Centralized prompt template manager.

    Loads .md template files, renders with variables, and logs all calls.
    """

    _templates: dict[str, str] = {}
    _log: list[PromptLog] = []
    _enable_log: bool = True

    @classmethod
    def get(cls, name: str, **kwargs: Any) -> str:
        """Load template and render with variables.

        Args:
            name: Template name relative to prompts dir (e.g. "skillgrade/difficulty_assessment")
            **kwargs: Variables to fill into template

        Returns:
            Rendered prompt string
        """
        template = cls._load(name)
        rendered = template.format(**kwargs)

        if cls._enable_log:
            cls._log.append(PromptLog(
                name=name,
                template=template,
                variables=kwargs,
                rendered=rendered,
            ))

        if os.environ.get("SKILLFLOW_DEBUG_PROMPTS"):
            console.print(f"\n[bold cyan][Prompt: {name}][/bold cyan]")
            preview = rendered[:500] + "..." if len(rendered) > 500 else rendered
            console.print(f"[dim]{preview}[/dim]\n")

        return rendered

    @classmethod
    def get_raw(cls, name: str) -> str:
        """Get raw template without rendering.

        Args:
            name: Template name

        Returns:
            Raw template string with placeholders
        """
        return cls._load(name)

    @classmethod
    def get_log(cls) -> list[PromptLog]:
        """Get all prompt rendering logs."""
        return list(cls._log)

    @classmethod
    def clear_log(cls) -> None:
        """Clear all logs."""
        cls._log.clear()

    @classmethod
    def set_logging(cls, enabled: bool) -> None:
        """Enable or disable prompt logging."""
        cls._enable_log = enabled

    @classmethod
    def list_templates(cls) -> list[str]:
        """List all available template names."""
        templates = []
        for md_file in _TEMPLATES_DIR.rglob("*.md"):
            rel = md_file.relative_to(_TEMPLATES_DIR)
            templates.append(str(rel.with_suffix("")))
        return sorted(templates)

    @classmethod
    def _load(cls, name: str) -> str:
        """Load template from file with caching.

        Args:
            name: Template name (e.g. "skillgrade/difficulty_assessment")

        Returns:
            Template string

        Raises:
            FileNotFoundError: If template file doesn't exist
        """
        if name not in cls._templates:
            template_path = _TEMPLATES_DIR / f"{name}.md"
            if not template_path.exists():
                raise FileNotFoundError(
                    f"Prompt template not found: {template_path}\n"
                    f"Available: {cls.list_templates()}"
                )
            cls._templates[name] = template_path.read_text(encoding="utf-8")

        return cls._templates[name]
