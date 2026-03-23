"""Local provider module."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from ..core.workspace import create_temp_workspace, cleanup_workspace, read_env_file
from ..types import WorkspaceFile, EnvironmentConfig


class LocalProvider:
    """Local environment provider.

    Creates temporary workspaces on the local filesystem for evaluation.
    This is the only supported provider in this Python version (no Docker).
    """

    def __init__(self):
        """Initialize the local provider."""
        pass

    async def setup(
        self,
        workspace_config: list[dict[str, Any]] | None = None,
        skill_paths: list[str] | None = None,
        env_vars: dict[str, str] | None = None,
    ) -> Path:
        """Set up a temporary workspace.

        Args:
            workspace_config: List of workspace file configurations
            skill_paths: Optional list of skill directory paths
            env_vars: Optional environment variables to export

        Returns:
            Path to the created workspace
        """
        workspace_files = []
        if workspace_config:
            for item in workspace_config:
                workspace_files.append(
                    WorkspaceFile(
                        src=item["src"],
                        dest=item["dest"],
                        chmod=item.get("chmod"),
                    )
                )

        workspace = create_temp_workspace(workspace_files, skill_paths or [])

        if env_vars:
            env_file = workspace / ".env"
            env_lines = [f"{k}={v}" for k, v in env_vars.items()]
            env_file.write_text("\n".join(env_lines))

        return workspace

    async def cleanup(self, workspace: Path | str) -> None:
        """Clean up a temporary workspace.

        Args:
            workspace: Path to the workspace to clean up
        """
        cleanup_workspace(Path(workspace))

    async def teardown(self) -> None:
        """Teardown the provider (no-op for local provider)."""
        pass

    async def run_command(
        self,
        workspace: Path | str,
        command: str,
        env: dict[str, str] | None = None,
        timeout: int = 60,
    ) -> tuple[str, str, int]:
        """Run a command in the workspace.

        This is a convenience method for running commands directly,
        though agents typically use the shell tool instead.

        Args:
            workspace: Path to the workspace
            command: Command to run
            env: Optional environment variables
            timeout: Maximum execution time in seconds

        Returns:
            Tuple of (stdout, stderr, exit_code)
        """
        import asyncio

        workspace = Path(workspace)

        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(workspace),
            env=env,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return (
                stdout.decode() if stdout else "",
                stderr.decode() if stderr else "",
                proc.returncode or 0,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise TimeoutError(f"Command timed out after {timeout}s")

    async def diagnose(self, workspace: Path | str) -> dict[str, Any]:
        """Get diagnostic information about the workspace.

        Args:
            workspace: Path to the workspace

        Returns:
            Dictionary with diagnostic information
        """
        import asyncio

        workspace = Path(workspace)

        if not workspace.exists():
            return {"error": "Workspace does not exist"}

        result = {
            "workspace": str(workspace),
            "exists": True,
            "files": [],
        }

        try:
            files = list(workspace.rglob("*"))
            result["file_count"] = len(files)
            result["files"] = [str(f.relative_to(workspace)) for f in files if f.is_file()][:50]

            proc = await asyncio.create_subprocess_shell(
                "df -h . && du -sh . 2>/dev/null || echo 'N/A'",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workspace),
            )
            stdout, _ = await proc.communicate()
            result["disk_usage"] = stdout.decode().strip()

        except Exception as e:
            result["error"] = str(e)

        return result


def load_workspace_env(workspace: Path | str) -> dict[str, str]:
    """Load environment variables from a workspace's .env file.

    Args:
        workspace: Path to the workspace

    Returns:
        Dictionary of environment variables
    """
    env_file = Path(workspace) / ".env"
    return read_env_file(env_file)
