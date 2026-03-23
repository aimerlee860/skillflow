"""LLM client wrapper for skillevol."""

import os
from typing import Optional

from anthropic import Anthropic
from openai import OpenAI


class LLMClient:
    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.7,
    ):
        self.provider = provider
        self.model = model
        self.temperature = temperature

        if provider == "anthropic":
            self.client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        else:
            self.client = OpenAI(
                api_key=api_key or os.environ.get("OPENAI_API_KEY"),
                base_url=base_url or os.environ.get("LLM_BASE_URL"),
            )

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        if self.provider == "anthropic":
            return self._generate_anthropic(prompt, system)
        return self._generate_openai(prompt, system)

    def _generate_openai(self, prompt: str, system: Optional[str] = None) -> str:
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

    def _generate_anthropic(self, prompt: str, system: Optional[str] = None) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
