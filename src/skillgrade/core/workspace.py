"""Workspace management module."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import WorkspaceFile


def discover_skill_dirs(skills_dir: Path) -> list[str]:
    """Scan a parent directory for skill subdirectories.

    Each subdirectory containing a SKILL.md is treated as an individual skill.

    Args:
        skills_dir: Parent directory containing skill subdirectories

    Returns:
        List of absolute paths to individual skill directories
    """
    skills_dir = Path(skills_dir).resolve()
    if not skills_dir.is_dir():
        return []

    result = []
    for child in sorted(skills_dir.iterdir()):
        if child.is_dir() and (child / "SKILL.md").exists():
            result.append(str(child))
    return result


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
    """Inject skill files into the workspace by copying.

    Copies skills into workspace/skills/<name>/ so that the FilesystemBackend
    with virtual_mode=True can access them. Only the target skill is injected
    — no leakage from ~/.agents/skills/ or ~/.claude/skills/.
    """
    skills_dir = workspace / "skills"

    for skill_path in skill_paths:
        skill_dir = Path(skill_path)
        if not skill_dir.exists():
            continue

        skill_name = skill_dir.name
        dest = skills_dir / skill_name
        shutil.copytree(skill_dir, dest, dirs_exist_ok=True)


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
