"""Base agent module."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Base class for all agents in skillgrade."""

    @abstractmethod
    async def run(
        self,
        instruction: str,
        workspace: str,
        timeout: int = 300,
    ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
        """Run the agent with the given instruction.

        Args:
            instruction: The instruction/prompt for the agent
            workspace: Path to the workspace directory
            timeout: Maximum execution time in seconds

        Returns:
            Tuple of (final_output, tool_call_logs, skill_tracking_logs)
        """
        ...
