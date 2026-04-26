from typing import AsyncIterator

import anthropic

from .interface import LLMProvider


class ClaudeProvider(LLMProvider):
    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
    ):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def function_call(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> dict:
        claude_tools = [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": {
                    "type": "object",
                    "properties": {k: {"type": v} for k, v in t["parameters"].items()},
                    "required": list(t["parameters"].keys()),
                },
            }
            for t in tools
        ]

        kwargs: dict = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": messages,
        }
        if claude_tools:
            kwargs["tools"] = claude_tools

        response = await self.client.messages.create(**kwargs)

        for block in response.content:
            if block.type == "tool_use":
                return {
                    "type": "function_call",
                    "name": block.name,
                    "arguments": block.input,
                }

        text = next((b.text for b in response.content if b.type == "text"), "")
        return {"type": "text", "content": text}

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=1024,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text
