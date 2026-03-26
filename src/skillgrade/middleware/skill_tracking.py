"""Skill Tracking Middleware for deepagents.

This middleware intercepts tool calls to track when skill files are accessed.
It's a cleaner alternative to the global variable approach, leveraging deepagents'
native middleware architecture.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, AgentState
from langchain_core.messages import ToolMessage

from ..core.skill_tracking import SkillTracker
from ..types import SkillAccessType, SkillTrackingSession


class SkillTrackingMiddleware(AgentMiddleware):
    """Middleware that tracks skill file access during agent execution.

    This middleware intercepts `read_file` tool calls to detect when
    skill files (SKILL.md, references/, scripts/, etc.) are accessed.

    Integration with deepagents:
    ```python
    from skillgrade.middleware import SkillTrackingMiddleware

    agent = create_deep_agent(
        middleware=[SkillTrackingMiddleware(skill_paths=["/skills/project/"])]
    )
    ```

    The middleware updates agent state with skill tracking information,
    which can be used by TriggerGrader for evaluation.
    """

    state_schema = AgentState

    def __init__(
        self,
        skill_paths: list[str],
        workspace: str | Path | None = None,
    ):
        """Initialize skill tracking middleware.

        Args:
            skill_paths: List of skill directory paths to track
            workspace: Optional workspace path (will be set at runtime if not provided)
        """
        self.skill_paths = skill_paths
        self.workspace = Path(workspace) if workspace else None

        # Initialize tracker with workspace if provided
        if workspace:
            self._tracker = SkillTracker(
                skill_paths=skill_paths,
                workspace=Path(workspace),
            )
        else:
            self._tracker = None

    def _detect_skill_access(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> tuple[str | None, SkillAccessType | None]:
        """Detect if a tool call is accessing a skill file.

        Args:
            tool_name: Name of the tool being called
            tool_args: Arguments passed to the tool

        Returns:
            Tuple of (skill_name, access_type) or (None, None)
        """
        if tool_name != "read_file":
            return None, None

        file_path = tool_args.get("file_path", "")
        if not file_path:
            return None, None

        normalized_path = self._normalize_file_path(file_path)

        # If we have a tracker, use it to detect skill access
        if self._tracker:
            return self._tracker.detect_skill_from_path(normalized_path)

        # Fallback: detect from skill paths directly
        path = Path(normalized_path)
        if not path.is_absolute() and self.workspace:
            path = self.workspace / path

        try:
            path = path.resolve()
        except (OSError, RuntimeError):
            return None, None

        for skill_path in self.skill_paths:
            skill_dir = Path(skill_path)
            if not skill_dir.is_absolute() and self.workspace:
                skill_dir = self.workspace / skill_dir

            try:
                skill_dir = skill_dir.resolve()
            except (OSError, RuntimeError):
                continue

            try:
                relative = path.relative_to(skill_dir)
                relative_str = str(relative)

                if relative_str == "SKILL.md":
                    return skill_dir.name, SkillAccessType.SKILL_MD
                elif relative_str.startswith("references/") or relative_str.startswith(
                    "references\\"
                ):
                    return skill_dir.name, SkillAccessType.REFERENCE
                elif relative_str.startswith("scripts/") or relative_str.startswith(
                    "scripts\\"
                ):
                    return skill_dir.name, SkillAccessType.SCRIPT
                elif relative_str.startswith("assets/") or relative_str.startswith(
                    "assets\\"
                ):
                    return skill_dir.name, SkillAccessType.ASSET
            except ValueError:
                continue

        return None, None

    def _normalize_file_path(self, file_path: str) -> str:
        """Normalize deepagents virtual paths into real workspace paths."""
        if not self.workspace:
            return file_path

        # deepagents FilesystemBackend in virtual_mode emits paths like
        # '/.claude/skills/<skill>/SKILL.md'. These are virtual paths rooted
        # at the workspace, not real filesystem absolute paths.
        if file_path.startswith("/.agents/") or file_path.startswith("/.claude/"):
            return str((self.workspace / file_path.lstrip("/")).resolve())

        return file_path

    def wrap_tool_call(
        self,
        request: Any,
        handler: Callable[[Any], ToolMessage],
    ) -> ToolMessage:
        """Synchronous tool call wrapper for skill tracking.

        Args:
            request: Tool call request with tool name, args, and runtime
            handler: Handler to execute the tool

        Returns:
            ToolMessage result from handler
        """
        # Extract tool info from request
        tool_name = ""
        tool_args = {}

        if hasattr(request, "tool"):
            tool = request.tool
            if hasattr(tool, "name"):
                tool_name = tool.name
            elif hasattr(tool, "__name__"):
                tool_name = tool.__name__

        if hasattr(request, "tool_call"):
            tool_call = request.tool_call
            if isinstance(tool_call, dict):
                tool_args = tool_call.get("args", {})

        # Detect skill file access
        skill_name, access_type = self._detect_skill_access(tool_name, tool_args)

        # Record access if it's a skill file
        if skill_name and access_type and self._tracker:
            self._tracker.record_access(
                file_path=self._normalize_file_path(tool_args.get("file_path", "")),
                tool_used=tool_name,
                skill_name=skill_name,
                access_type=access_type,
            )

        # Execute the tool
        return handler(request)

    async def awrap_tool_call(
        self,
        request: Any,
        handler: Callable[[Any], Awaitable[ToolMessage]],
    ) -> ToolMessage:
        """Asynchronous tool call wrapper for skill tracking.

        Args:
            request: Tool call request with tool name, args, and runtime
            handler: Async handler to execute the tool

        Returns:
            ToolMessage result from handler
        """
        # Extract tool info from request
        tool_name = ""
        tool_args = {}

        if hasattr(request, "tool"):
            tool = request.tool
            if hasattr(tool, "name"):
                tool_name = tool.name
            elif hasattr(tool, "__name__"):
                tool_name = tool.__name__

        if hasattr(request, "tool_call"):
            tool_call = request.tool_call
            if isinstance(tool_call, dict):
                tool_args = tool_call.get("args", {})

        # Detect skill file access
        skill_name, access_type = self._detect_skill_access(tool_name, tool_args)

        # Record access if it's a skill file
        if skill_name and access_type and self._tracker:
            self._tracker.record_access(
                file_path=self._normalize_file_path(tool_args.get("file_path", "")),
                tool_used=tool_name,
                skill_name=skill_name,
                access_type=access_type,
            )

        # Execute the tool
        return await handler(request)

    def get_tracker(self) -> SkillTracker | None:
        """Get the current skill tracker instance."""
        return self._tracker

    def get_skill_tracking_data(self) -> list[dict[str, Any]]:
        """Get skill tracking sessions as serializable data.

        Returns:
            List of skill tracking session dicts
        """
        if self._tracker:
            return [session.to_dict() for session in self._tracker.get_all_sessions()]
        return []


class SkillTrackingState(AgentState):
    """Extended agent state with skill tracking data."""

    skill_tracking_sessions: list[dict[str, Any]]
    """List of skill tracking sessions from SkillTrackingMiddleware."""


__all__ = ["SkillTrackingMiddleware", "SkillTrackingState"]
