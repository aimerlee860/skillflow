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
    ):
        """Initialize the OpenAI Functions Agent.

        Args:
            model_name: Override model name
            base_url: Override base URL for API
            api_key: Override API key
            max_iterations: Maximum number of agent iterations
            max_execution_time: Maximum execution time in seconds
        """
        self.llm_client = LLMClient(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
        )
        self.max_iterations = max_iterations
        self.max_execution_time = max_execution_time

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
    ) -> tuple[str, list[dict[str, Any]]]:
        """Run the agent with the given instruction.

        Args:
            instruction: The instruction/prompt for the agent
            workspace: Path to the workspace directory
            timeout: Maximum execution time in seconds

        Returns:
            Tuple of (final_output, tool_call_logs)
        """
        original_cwd = Path.cwd()
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

            return output or "No output generated", logs

        finally:
            os.chdir(original_cwd)

    def get_model_name(self) -> str:
        """Get the model name being used."""
        return self.llm_client.get_model_name()
