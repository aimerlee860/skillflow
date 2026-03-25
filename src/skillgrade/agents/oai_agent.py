"""OpenAI Functions Agent implementation using LangGraph."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

from .base import BaseAgent
from ..llm.client import LLMClient
from ..tools import shell, read_file, write_file, glob_files
from ..tools.file_ops import set_skill_tracker, get_skill_tracker
from ..core.skill_tracking import SkillTracker


class OAIAgent(BaseAgent):
    """OpenAI Functions Agent for skillgrade.

    Uses LangGraph's pre-built ReAct agent with OpenAI function calling.
    Provides tools for shell execution, file operations, and glob matching.
    """

    def __init__(
        self,
        model_name: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        max_iterations: int = 50,
        max_execution_time: int = 300,
        skill_paths: list[str] | None = None,
        enable_tracking: bool = True,
    ):
        """Initialize the OpenAI Functions Agent.

        Args:
            model_name: Override model name
            base_url: Override base URL for API
            api_key: Override API key
            max_iterations: Maximum number of agent iterations
            max_execution_time: Maximum execution time in seconds
            skill_paths: Optional list of skill paths for tracking
            enable_tracking: Whether to enable skill tracking
        """
        self.llm_client = LLMClient(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
        )
        self.max_iterations = max_iterations
        self.max_execution_time = max_execution_time
        self.skill_paths = skill_paths or []
        self.enable_tracking = enable_tracking

        # Skill tracker instance (created per run)
        self._skill_tracker: SkillTracker | None = None

        self.tools = [shell, read_file, write_file, glob_files]

        self.graph = create_react_agent(
            model=self.llm_client.chat,
            tools=self.tools,
        )

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
        original_cwd = Path.cwd()

        # Initialize skill tracker for this run
        if self.enable_tracking and self.skill_paths:
            self._skill_tracker = SkillTracker(
                skill_paths=self.skill_paths,
                workspace=Path(workspace),
            )
            # Set global tracker for tools to access
            set_skill_tracker(self._skill_tracker)

        try:
            os.chdir(workspace)

            config = {
                "configurable": {"thread_id": "default"},
                "recursion_limit": self.max_iterations,
            }

            if timeout:
                config["max_execution_time"] = timeout

            result = await self.graph.ainvoke(
                {"messages": [HumanMessage(content=instruction)]},
                config=config,
            )

            messages = result.get("messages", [])
            output = ""
            logs = []
            skill_tracking_logs = []

            for msg in messages:
                if hasattr(msg, "type"):
                    if msg.type == "ai" and not output:
                        output = msg.content if hasattr(msg, "content") else str(msg)
                    elif msg.type == "tool":
                        logs.append(
                            {
                                "type": "tool_call",
                                "data": {
                                    "tool": getattr(msg, "name", "unknown"),
                                    "tool_input": getattr(msg, "tool_input", ""),
                                    "output": msg.content if hasattr(msg, "content") else str(msg),
                                },
                            }
                        )

            # Generate skill tracking logs
            if self._skill_tracker:
                skill_tracking_logs = [
                    {
                        "type": "skill_tracking",
                        "data": session.to_dict(),
                    }
                    for session in self._skill_tracker.get_all_sessions()
                ]

            return output or "No output generated", logs, skill_tracking_logs

        finally:
            os.chdir(original_cwd)
            # Clear global tracker after run
            set_skill_tracker(None)

    def get_model_name(self) -> str:
        """Get the model name being used."""
        return self.llm_client.get_model_name()

    def get_skill_tracker(self) -> SkillTracker | None:
        """Get the skill tracker instance from the last run."""
        return self._skill_tracker
