"""LLM client wrapper for skillevol."""

import os
from typing import Optional

from openai import OpenAI


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

        self.client = OpenAI(
            api_key=api_key or os.environ.get("LLM_API_KEY"),
            base_url=base_url or os.environ.get("LLM_BASE_URL"),
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
