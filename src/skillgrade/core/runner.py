"""Evaluation runner module - manages temporary workspace and execution."""

from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import (
    load_eval_config,
    load_eval_config_from_path,
    save_eval_config,
)
from .generator import generate_eval_plan
from .skills import detect_skills
from .workspace import create_temp_workspace, cleanup_workspace


class EvalRunner:
    """Manages the evaluation workflow including temp workspace setup."""

    def __init__(
        self,
        skill_dir: Path,
        config_path: Path | None = None,
        output_dir: Path | None = None,
        keep_workspaces: bool = False,
    ):
        """Initialize the eval runner.

        Args:
            skill_dir: Path to the skill directory (contains SKILL.md)
            config_path: Optional path to eval.yaml config file
            output_dir: Optional custom output directory (defaults to $TMPDIR/skillgrade/<name>)
            keep_workspaces: Whether to keep workspace copies for debugging
        """
        self.skill_dir = skill_dir.resolve()
        self.config_path = config_path
        self.keep_workspaces = keep_workspaces

        self._temp_dir: Path | None = None
        self._eval_config_path: Path | None = None

        skill_name = self.skill_dir.name
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_dir = (
                Path(tempfile.gettempdir()) / "skillgrade" / f"{skill_name}_{timestamp}"
            )
        else:
            self.output_dir = output_dir.resolve()

        self.results_dir = self.output_dir / "results"
        self.workspaces_dir = self.output_dir / "workspaces"

    async def setup(self) -> tuple[Path, Path]:
        """Set up the temporary workspace and prepare config.

        Creates:
        - temp_dir/eval.yaml
        - temp_dir/SKILL.md (copied from skill_dir)
        - output_dir/results/
        - output_dir/workspaces/ (if keep_workspaces)

        Returns:
            Tuple of (temp_dir, config_path)
        """
        self._temp_dir = Path(tempfile.mkdtemp(prefix=f"skillgrade_{self.skill_dir.name}_"))
        self._eval_config_path = self._temp_dir / "eval.yaml"

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)

        if self.keep_workspaces:
            self.workspaces_dir.mkdir(parents=True, exist_ok=True)

        skill_md = self.skill_dir / "SKILL.md"
        if skill_md.exists():
            shutil.copy2(skill_md, self._temp_dir / "SKILL.md")

        # Check for eval.yaml in skill_dir (auto-detect if not explicitly provided)
        eval_yaml_in_skill = self.skill_dir / "eval.yaml"
        config_source = self.config_path or (
            eval_yaml_in_skill if eval_yaml_in_skill.exists() else None
        )

        if config_source:
            config = load_eval_config_from_path(config_source)
            # Set skill name from skill_dir if not already set
            if not config.skill:
                config.skill = self.skill_dir.name
            save_eval_config(config, self._eval_config_path)
        else:
            # Generate evaluation configuration using deep analysis
            config = generate_eval_plan(self.skill_dir)
            save_eval_config(config, self._eval_config_path)

        return self._temp_dir, self._eval_config_path

    def get_skill_paths(self) -> list[str]:
        """Get list of skill paths to inject into workspace.

        Returns:
            List of skill directory paths
        """
        detected = detect_skills(self.skill_dir)
        paths = []
        for skill in detected:
            skill_path = Path(skill["path"]).parent
            if str(skill_path) not in paths:
                paths.append(str(skill_path))
        return paths

    def get_config(self) -> Any:
        """Load and return the eval configuration.

        Returns:
            EvalConfig object
        """
        if self._eval_config_path is None:
            raise RuntimeError("Runner not set up. Call setup() first.")
        return load_eval_config_from_path(self._eval_config_path, self._temp_dir)

    def get_temp_dir(self) -> Path | None:
        """Get the temporary directory path.

        Returns:
            Path to temp directory or None if not set up
        """
        return self._temp_dir

    def cleanup(self) -> None:
        """Clean up temporary workspace.

        Unless keep_workspaces is True, removes the temp directory.
        The output_dir is kept for results access.
        """
        if self._temp_dir and self._temp_dir.exists():
            if not self.keep_workspaces:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None

    def __enter__(self) -> "EvalRunner":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.cleanup()


def get_default_output_dir(skill_name: str) -> Path:
    """Get the default output directory for a skill.

    Args:
        skill_name: Name of the skill

    Returns:
        Path to the default output directory
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(tempfile.gettempdir()) / "skillgrade" / f"{skill_name}_{timestamp}"
