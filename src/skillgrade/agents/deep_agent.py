"""Deep Agent implementation using deepagents framework with native skill support."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from .base import BaseAgent
from ..llm.client import LLMClient
from ..tools import shell
from ..core.skill_tracking import SkillTracker
from ..middleware.skill_tracking import SkillTrackingMiddleware
from prompts import PromptManager

# Note: We don't import read_file, write_file, glob_files here because
# deepagents' FilesystemMiddleware provides these tools with proper
# virtual path handling via the backend. Using custom tools would break
# skill file reading since SkillsMiddleware injects virtual paths like
# /.agents/skills/<name>/SKILL.md that need to be resolved via backend.


class DeepAgent(BaseAgent):
    """Deep Agent for skillgrade using deepagents framework.

    Uses deepagents' create_deep_agent with native skill support via SkillsMiddleware.
    The agent receives skill metadata in its system prompt and can read SKILL.md
    files on demand using the read_file tool.

    Key features:
    - Progressive disclosure: Skills are listed in system prompt, agent reads details on demand
    - Native skill support via deepagents SkillsMiddleware
    - Skill tracking via native middleware (wrap_tool_call hook)
    - No global state - uses deepagents middleware architecture
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
        verbose: bool = False,
    ):
        """Initialize the Deep Agent.

        Args:
            model_name: Override model name (supports provider:model format)
            base_url: Override base URL for API
            api_key: Override API key
            max_iterations: Maximum number of agent iterations
            max_execution_time: Maximum execution time in seconds
            skill_paths: Optional list of skill paths for native skill support
            enable_tracking: Whether to enable skill tracking
            verbose: Show debug information
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
        self.verbose = verbose

        # Skill tracking middleware (created per run with workspace context)
        self._tracking_middleware: SkillTrackingMiddleware | None = None

        # Build a concrete chat model instance so deepagents uses the same
        # LLM configuration as the rest of skillgrade instead of falling back
        # to provider-specific env vars like OPENAI_API_KEY / Anthropic keys.
        self._chat_model = self.llm_client.chat

        # Custom system prompt for skillgrade context
        self._custom_system_prompt = PromptManager.get_raw("skillgrade/agent_system")

        # Available tools
        # Note: File tools (read_file, write_file, glob, grep, ls) are provided by
        # deepagents' FilesystemMiddleware, which handles virtual path resolution.
        # We only add shell tool here as it's not provided by default.
        self.tools = [shell]

        # Create the deep agent graph (will be configured with skills at run time)
        self._graph = None

    def _create_agent_with_skills(
        self,
        workspace: str,
        skill_sources: list[str],
    ):
        """Create a deep agent configured with skill sources.

        Args:
            workspace: Path to the workspace directory
            skill_sources: List of skill source paths

        Returns:
            Compiled deep agent graph
        """
        # Skills are symlinked at workspace/skills/<name>
        skill_source_paths = [
            "/skills/",
        ]

        # Create filesystem backend for skill loading
        # Use virtual_mode=True for proper path handling
        backend = FilesystemBackend(
            root_dir=workspace,
            virtual_mode=True,
        )

        # Debug: verify backend can access skills and subdirectories
        if self.verbose:
            from rich.console import Console as _Console
            _dbg = _Console()
            try:
                items = backend.ls_info("/skills/")
                _dbg.print(f"[dim]  [DEBUG] ls_info('/skills/') → {len(items)} items[/dim]")
                for item in items:
                    _dbg.print(f"[dim]    {item.get('path')} is_dir={item.get('is_dir')}[/dim]")
                for item in items:
                    if item.get("is_dir"):
                        skill_md_path = item["path"].rstrip("/") + "/SKILL.md"
                        resp = backend.download_files([skill_md_path])
                        r = resp[0]
                        status = f"✓ {len(r.content)}B" if r.content else f"✗ {r.error}"
                        _dbg.print(f"[dim]    download({skill_md_path}) → {status}[/dim]")

                        # Test subdirectory access
                        skill_dir_path = item["path"]
                        sub_items = backend.ls_info(skill_dir_path)
                        _dbg.print(f"[dim]    ls_info('{skill_dir_path}') → {len(sub_items)} items[/dim]")
                        for sub in sub_items:
                            _dbg.print(f"[dim]      {sub.get('path')} is_dir={sub.get('is_dir')}[/dim]")
                        # Test reading a file in subdirectory
                        for sub in sub_items:
                            if sub.get("is_dir") and "scripts" in sub.get("path", ""):
                                scripts = backend.ls_info(sub["path"])
                                for s in scripts:
                                    if not s.get("is_dir"):
                                        sr = backend.download_files([s["path"]])
                                        st = f"✓ {len(sr[0].content)}B" if sr[0].content else f"✗ {sr[0].error}"
                                        _dbg.print(f"[dim]      download({s['path']}) → {st}[/dim]")
            except Exception as e:
                _dbg.print(f"[dim]  [DEBUG] backend error: {e}[/dim]")

        # Build middleware stack
        middleware = []
        if self.enable_tracking and skill_sources:
            # Use workspace-injected skill paths for tracking
            workspace_skill_paths = []
            for skill_source in skill_sources:
                skill_name = Path(skill_source).name
                workspace_skill_paths.append(str(Path(workspace) / "skills" / skill_name))

            # Create tracking middleware with workspace paths
            self._tracking_middleware = SkillTrackingMiddleware(
                skill_paths=workspace_skill_paths,
                workspace=workspace,
            )
            middleware.append(self._tracking_middleware)

        # Create the deep agent with skills and tracking middleware
        agent = create_deep_agent(
            model=self._chat_model,
            tools=self.tools,
            system_prompt=self._custom_system_prompt,
            skills=skill_source_paths if skill_source_paths else None,
            backend=backend,
            middleware=middleware if middleware else None,
        )

        return agent

    @staticmethod
    def _extract_tool_call_fields(tool_call: Any) -> tuple[str, dict[str, Any], str]:
        """Extract tool call fields from either dict or object-style payloads."""
        if isinstance(tool_call, dict):
            return (
                str(tool_call.get("name", "unknown")),
                dict(tool_call.get("args", {}) or {}),
                str(tool_call.get("id", "")),
            )

        return (
            str(getattr(tool_call, "name", "unknown")),
            dict(getattr(tool_call, "args", {}) or {}),
            str(getattr(tool_call, "id", "")),
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
        workspace_path = Path(workspace)

        try:
            os.chdir(workspace)

            # Create agent with skill sources and tracking middleware
            if self.skill_paths:
                self._graph = self._create_agent_with_skills(workspace, self.skill_paths)
            else:
                # No skills, create basic agent
                self._graph = create_deep_agent(
                    model=self._chat_model,
                    tools=self.tools,
                    system_prompt=self._custom_system_prompt,
                )

            config = {
                "configurable": {"thread_id": "default"},
                "recursion_limit": self.max_iterations,
            }

            if timeout:
                config["max_execution_time"] = timeout

            # Use astream with dynamic early exit
            soft_limit = 10
            best_output = ""
            messages = []
            iteration = 0

            if self.verbose:
                from rich.console import Console as _Console
                _dbg = _Console()
                _dbg.print(f"[dim]  [DEBUG] skill_paths: {self.skill_paths}[/dim]")

            async for event in self._graph.astream(
                {"messages": [HumanMessage(content=instruction)]},
                config=config,
                stream_mode="values",
            ):
                messages = event.get("messages", messages)
                iteration += 1

                # Check last AI message for natural completion
                last_ai = next(
                    (m for m in reversed(messages) if getattr(m, "type", None) == "ai"),
                    None,
                )
                if last_ai:
                    content = getattr(last_ai, "content", "") or ""
                    tool_calls = getattr(last_ai, "tool_calls", [])
                    if content and not tool_calls:
                        best_output = content
                        if iteration > soft_limit:
                            if self.verbose:
                                _dbg.print(f"[dim]  [DEBUG] soft exit at iteration {iteration}, output len={len(best_output)}[/dim]")
                            break

            if self.verbose:
                _dbg.print(f"[dim]  [DEBUG] total iterations: {iteration}, messages: {len(messages)}, output len: {len(best_output)}[/dim]")

            output = best_output
            logs = []
            skill_tracking_logs = []

            # Log user input
            logs.append({
                "type": "user_input",
                "data": {
                    "content": instruction,
                },
            })

            # Process all messages
            round_num = 0
            for i, msg in enumerate(messages):
                msg_type = getattr(msg, "type", None)

                if msg_type == "human":
                    pass

                elif msg_type == "ai":
                    content = getattr(msg, "content", "") or ""
                    tool_calls = getattr(msg, "tool_calls", [])

                    if content:
                        logs.append({
                            "type": "ai_thinking",
                            "data": {
                                "round": round_num,
                                "content": content,
                            },
                        })

                    if tool_calls:
                        for tc in tool_calls:
                            tool_name, tool_args, tool_id = self._extract_tool_call_fields(tc)
                            logs.append({
                                "type": "tool_call_decision",
                                "data": {
                                    "round": round_num,
                                    "tool": tool_name,
                                    "args": tool_args,
                                    "id": tool_id,
                                },
                            })

                    round_num += 1
                    output = content or output

                elif msg_type == "tool":
                    logs.append({
                        "type": "tool_result",
                        "data": {
                            "tool": getattr(msg, "name", "unknown"),
                            "tool_call_id": getattr(msg, "tool_call_id", ""),
                            "output": msg.content if hasattr(msg, "content") else str(msg),
                        },
                    })

                elif msg_type == "system":
                    content = getattr(msg, "content", "")
                    if content:
                        logs.append({
                            "type": "system_message",
                            "data": {
                                "content": content[:2000],
                            },
                        })

            if output:
                logs.append({
                    "type": "agent_result",
                    "data": {
                        "output": output,
                    },
                })

            # Get skill tracking data from middleware
            if self._tracking_middleware:
                skill_tracking_logs = [
                    {
                        "type": "skill_tracking",
                        "data": session,
                    }
                    for session in self._tracking_middleware.get_skill_tracking_data()
                ]

            return output or "No output generated", logs, skill_tracking_logs

        finally:
            os.chdir(original_cwd)
            self._tracking_middleware = None

    def get_model_name(self) -> str:
        """Get the model name being used."""
        return self.llm_client.get_model_name()

    def get_skill_tracker(self) -> SkillTracker | None:
        """Get the skill tracker instance from the middleware.

        Note: This returns the internal tracker from the middleware for compatibility.
        """
        if self._tracking_middleware:
            return self._tracking_middleware.get_tracker()
        return None
