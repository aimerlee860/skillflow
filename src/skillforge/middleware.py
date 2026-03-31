"""Middleware for optimizing token usage in agent conversations."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)
from langchain_core.messages import AIMessage, AnyMessage


class ThinkingStripMiddleware(AgentMiddleware):
    """Strip thinking content from historical AI messages to reduce token usage.

    For AIMessages that have tool_calls, the content field contains the model's
    reasoning/thinking text which is useful for the current turn but becomes
    redundant in subsequent turns (the tool_calls and ToolMessages carry the
    essential information).

    This middleware keeps the content of the most recent N messages intact
    (preserving fresh context) and strips content from older AIMessages
    that have tool_calls.

    Args:
        keep_recent: Number of recent messages to preserve unchanged.
            Defaults to 4 (covers ~2 recent agent turns).
    """

    def __init__(self, keep_recent: int = 4) -> None:
        self.keep_recent = keep_recent

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any]:
        """Strip thinking content from older AI messages before sending to LLM."""
        messages = request.messages
        if len(messages) <= self.keep_recent + 1:
            return await handler(request)

        cutoff = len(messages) - self.keep_recent
        modified: list[AnyMessage] = []
        changed = False

        for i, msg in enumerate(messages):
            if (
                i < cutoff
                and isinstance(msg, AIMessage)
                and msg.tool_calls
                and msg.content
            ):
                # Strip content from historical AI messages that have tool_calls
                stripped = msg.model_copy(update={"content": ""})
                modified.append(stripped)
                changed = True
            else:
                modified.append(msg)

        if changed:
            request = request.override(messages=modified)

        return await handler(request)
