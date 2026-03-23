"""Workspace management module."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import WorkspaceFile


def create_temp_workspace(
    workspace_files: list[WorkspaceFile], skill_paths: list[str] | None = None
) -> Path:
    """Create a temporary workspace with the specified files.

    Args:
        workspace_files: List of files to copy into the workspace
        skill_paths: Optional list of skill directory paths to inject

    Returns:
        Path to the created temporary workspace
    """
    workspace = Path(tempfile.mkdtemp(prefix="skillgrade_"))

    for file_spec in workspace_files:
        src = Path(file_spec.src)
        dest = workspace / file_spec.dest

        if not src.exists():
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)

        if src.is_dir():
            shutil.copytree(src, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dest)

        if file_spec.chmod:
            mode = int(file_spec.chmod.replace("+x", "111", 1), 8)
            os.chmod(dest, mode)

    if skill_paths:
        _inject_skills(workspace, skill_paths)

    return workspace


def _inject_skills(workspace: Path, skill_paths: list[str]) -> None:
    """Inject skill files into the workspace.

    Creates the standard skill discovery paths:
    - .agents/skills/
    - .claude/skills/
    """
    agents_dir = workspace / ".agents" / "skills"
    claude_dir = workspace / ".claude" / "skills"

    for skill_path in skill_paths:
        skill_dir = Path(skill_path)
        if not skill_dir.exists():
            continue

        skill_name = skill_dir.name
        _copy_skill_to_path(skill_dir, agents_dir / skill_name)
        _copy_skill_to_path(skill_dir, claude_dir / skill_name)


def _copy_skill_to_path(src: Path, dest: Path) -> None:
    """Copy a skill directory to a destination."""
    dest.mkdir(parents=True, exist_ok=True)

    for item in src.iterdir():
        dest_item = dest / item.name
        if item.is_dir():
            shutil.copytree(item, dest_item, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest_item)


def cleanup_workspace(workspace: Path) -> None:
    """Clean up a temporary workspace.

    Args:
        workspace: Path to the workspace to clean up
    """
    if workspace.exists() and workspace.name.startswith("skillgrade_"):
        shutil.rmtree(workspace, ignore_errors=True)


def read_env_file(env_path: Path) -> dict[str, str]:
    """Read and parse a .env file.

    Supports formats:
    - KEY=VALUE
    - KEY="VALUE"
    - KEY='VALUE'
    - # comments
    - blank lines
    """
    if not env_path.exists():
        return {}

    env_vars = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'\"")

            if key:
                env_vars[key] = value

    return env_vars
