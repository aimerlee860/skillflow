"""LLM client module."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load environment variables from .env file in project root
# Path: src/skillgrade/llm/client.py -> parent=llm -> parent=skillgrade -> parent=src -> parent=project_root
_project_root = Path(__file__).resolve().parent.parent.parent.parent
_env_path = _project_root / ".env"
load_dotenv(_env_path)

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_openai import ChatOpenAI


def _should_bypass_proxy(url: str, no_proxy: str) -> bool:
    """Check if URL should bypass proxy based on no_proxy setting.

    Args:
        url: The URL to check
        no_proxy: Comma-separated list of hosts to bypass proxy

    Returns:
        True if URL should bypass proxy
    """
    if not no_proxy:
        return False

    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.hostname or parsed.netloc.split(":")[0]

    # Handle patterns like .example.com (matches subdomains)
    for pattern in no_proxy.split(","):
        pattern = pattern.strip()
        if not pattern:
            continue

        # Wildcard pattern like .example.com
        if pattern.startswith("."):
            if host.endswith(pattern) or host == pattern[1:]:
                return True
        # Exact match
        elif host == pattern:
            return True
        # Pattern without dot prefix matches host or subdomain
        elif host.endswith("." + pattern):
            return True

    return False


def _get_proxy_client() -> tuple[httpx.Client | None, httpx.AsyncClient | None]:
    """Create httpx clients with proxy settings from environment variables.

    Reads: http_proxy, https_proxy, no_proxy

    Returns:
        Tuple of (sync_client, async_client) or (None, None) if no proxy configured
    """
    http_proxy = os.environ.get("http_proxy") or os.environ.get("HTTP_PROXY")
    https_proxy = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")
    no_proxy = os.environ.get("no_proxy") or os.environ.get("NO_PROXY")

    if not (http_proxy or https_proxy):
        return None, None

    # Check if LLM_BASE_URL should bypass proxy
    llm_base_url = os.environ.get("LLM_BASE_URL", "")
    if no_proxy and _should_bypass_proxy(llm_base_url, no_proxy):
        return None, None

    # Use https_proxy as the primary proxy (most APIs use https)
    proxy_url = https_proxy or http_proxy

    sync_client = httpx.Client(proxy=proxy_url, timeout=120.0)
    async_client = httpx.AsyncClient(proxy=proxy_url, timeout=120.0)

    return sync_client, async_client


class LLMClient:
    """Client for interacting with OpenAI-compatible LLM APIs."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model_name: str | None = None,
    ):
        """Initialize LLM client.

        Args:
            base_url: Base URL for the API (defaults to LLM_BASE_URL env var)
            api_key: API key (defaults to LLM_API_KEY env var)
            model_name: Model name (defaults to LLM_MODEL_NAME env var)
        """
        self.base_url = base_url or os.environ["LLM_BASE_URL"]
        self.api_key = api_key or os.environ["LLM_API_KEY"]
        self.model_name = model_name or os.environ.get("LLM_MODEL_NAME", "gpt-4o")

    @property
    def chat(self) -> ChatOpenAI:
        """Get a ChatOpenAI instance with proxy support."""
        sync_client, async_client = _get_proxy_client()

        return ChatOpenAI(
            model=self.model_name,
            base_url=self.base_url,
            api_key=self.api_key,
            temperature=0,
            max_retries=3,
            http_client=sync_client,
            http_async_client=async_client,
        )

    async def achat(
        self,
        messages: list[BaseMessage],
        **kwargs: Any,
    ) -> ChatResult:
        """Async chat completion.

        Args:
            messages: List of chat messages
            **kwargs: Additional arguments for the API

        Returns:
            ChatResult from the model
        """
        return await self.chat.ainvoke(messages, **kwargs)

    def with_structured_output(self, schema: type) -> Any:
        """Create a model that returns structured output.

        Args:
            schema: Pydantic model or dict schema for output

        Returns:
            Model configured for structured output
        """
        return self.chat.with_structured_output(schema)

    def get_model_name(self) -> str:
        """Get the current model name."""
        return self.model_name


def get_llm_client(
    base_url: str | None = None,
    api_key: str | None = None,
    model_name: str | None = None,
) -> LLMClient:
    """Factory function to create an LLM client.

    Args:
        base_url: Optional base URL override
        api_key: Optional API key override
        model_name: Optional model name override

    Returns:
        Configured LLMClient instance
    """
    return LLMClient(base_url=base_url, api_key=api_key, model_name=model_name)


def validate_llm_config() -> bool:
    """Validate that required LLM environment variables are set.

    Returns:
        True if configuration is valid, False otherwise
    """
    required = ["LLM_BASE_URL", "LLM_API_KEY"]
    return all(os.environ.get(var) for var in required)
