import json
from typing import AsyncIterator

from openai import AsyncOpenAI

from .interface import LLMProvider


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def function_call(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> dict:
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": {
                        "type": "object",
                        "properties": {
                            k: {"type": v, "description": k}
                            for k, v in t["parameters"].items()
                        },
                        "required": list(t["parameters"].keys()),
                    },
                },
            }
            for t in tools
        ]

        kwargs: dict = {"model": self.model, "messages": messages}
        if openai_tools:
            kwargs["tools"] = openai_tools
            kwargs["tool_choice"] = "auto"

        response = await self.client.chat.completions.create(**kwargs)
        msg = response.choices[0].message

        if msg.tool_calls:
            tc = msg.tool_calls[0]
            return {
                "type": "function_call",
                "name": tc.function.name,
                "arguments": json.loads(tc.function.arguments),
            }
        return {"type": "text", "content": msg.content or ""}

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
        )
        async for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
