"""LLM client wrapper for skillevol."""

import os
from typing import Optional

import httpx
from openai import OpenAI


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

    # Build proxy mapping
    proxies = {}
    if http_proxy:
        proxies["http://"] = http_proxy
    if https_proxy:
        proxies["https://"] = https_proxy

    return httpx.Client(proxies=proxies, timeout=120.0)


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
