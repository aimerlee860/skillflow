"""Deterministic grader implementation."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .base import BaseGrader
from ..types import GraderConfig, GraderResult


class DeterministicGrader(BaseGrader):
    """Grader that executes a Python script to evaluate results.

    The Python script must output JSON to stdout with the following format:
    {
        "score": 0.0-1.0,
        "details": "Description of results",
        "checks": [
            {"name": "check-name", "passed": true, "message": "Description"}
        ]
    }
    """

    async def grade(
        self,
        workspace: Path | str,
        config: GraderConfig,
        logs: list[dict[str, Any]],
    ) -> GraderResult:
        """Execute the grader script and parse results.

        Args:
            workspace: Path to the workspace directory
            config: Grader configuration with run script
            logs: Execution logs (not used by deterministic grader)

        Returns:
            GraderResult with score and details
        """
        workspace = Path(workspace)

        if not config.run:
            return GraderResult(
                grader_type="deterministic",
                score=0.0,
                weight=config.weight,
                details="No run script configured",
            )

        try:
            result = await self._run_script(config.run, workspace)
            return GraderResult(
                grader_type="deterministic",
                score=result.get("score", 0.0),
                weight=config.weight,
                details=result.get("details", ""),
                checks=result.get("checks"),
            )

        except Exception as e:
            return GraderResult(
                grader_type="deterministic",
                score=0.0,
                weight=config.weight,
                details=f"Grader execution error: {str(e)}",
            )

    async def _run_script(self, script_content: str, workspace: Path) -> dict[str, Any]:
        """Run the grader script in a subprocess.

        Args:
            script_content: Python script content to execute
            workspace: Working directory for the script

        Returns:
            Parsed JSON output from the script
        """
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            script_content,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(workspace),
        )

        stdout, stderr = await proc.communicate()
        output = stdout.decode().strip()
        error_output = stderr.decode().strip()

        if proc.returncode != 0 and error_output:
            raise RuntimeError(f"Script error: {error_output}")

        try:
            return json.loads(output)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON output: {e}\nOutput: {output}")


def run_deterministic_grader_sync(
    script_content: str,
    workspace: Path,
    timeout: int = 60,
) -> dict[str, Any]:
    """Synchronous version of deterministic grader for simpler use cases.

    Args:
        script_content: Python script to execute
        workspace: Working directory
        timeout: Maximum execution time in seconds

    Returns:
        Parsed JSON result from the grader
    """
    try:
        result = subprocess.run(
            [sys.executable, "-c", script_content],
            capture_output=True,
            text=True,
            cwd=str(workspace),
            timeout=timeout,
        )

        if result.returncode != 0 and result.stderr:
            raise RuntimeError(f"Script error: {result.stderr}")

        return json.loads(result.stdout.strip())

    except subprocess.TimeoutExpired:
        raise RuntimeError("Grader script timed out")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON output: {e}\nOutput: {result.stdout}")
