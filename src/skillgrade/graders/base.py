"""Base grader module."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ..types import GraderConfig, GraderResult


class BaseGrader(ABC):
    """Base class for all graders in skillgrade."""

    @abstractmethod
    async def grade(
        self,
        workspace: Path | str,
        config: GraderConfig,
        logs: list[dict[str, Any]],
    ) -> GraderResult:
        """Evaluate the agent's work.

        Args:
            workspace: Path to the workspace directory
            config: Grader configuration
            logs: Execution logs from the agent

        Returns:
            GraderResult with score and details
        """
        ...
