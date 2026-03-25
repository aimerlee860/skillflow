"""LLM client wrapper for skillevol."""

import os
from typing import Optional
from urllib.parse import urlparse

import httpx
from openai import OpenAI


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


def _get_proxy_http_client() -> httpx.Client | None:
    """Create httpx client with proxy settings from environment variables.

    Reads: http_proxy, https_proxy, no_proxy

    Returns:
        httpx.Client with proxy configured, or None if no proxy set
    """
    http_proxy = os.environ.get("http_proxy") or os.environ.get("HTTP_PROXY")
    https_proxy = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")
    no_proxy = os.environ.get("no_proxy") or os.environ.get("NO_PROXY")

    if not (http_proxy or https_proxy):
        return None

    # Check if LLM_BASE_URL should bypass proxy
    llm_base_url = os.environ.get("LLM_BASE_URL", "")
    if no_proxy and _should_bypass_proxy(llm_base_url, no_proxy):
        return None

    # Use https_proxy as the primary proxy (most APIs use https)
    proxy_url = https_proxy or http_proxy

    return httpx.Client(proxy=proxy_url, timeout=120.0)


class LLMClient:
    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.7,
    ):
        self.model = model or os.environ.get("LLM_MODEL_NAME", "gpt-4o")
        self.temperature = temperature

        # Get proxy client if configured
        http_client = _get_proxy_http_client()

        self.client = OpenAI(
            api_key=api_key or os.environ.get("LLM_API_KEY"),
            base_url=base_url or os.environ.get("LLM_BASE_URL"),
            http_client=http_client,
        )

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
        )
        return response.choices[0].message.content
