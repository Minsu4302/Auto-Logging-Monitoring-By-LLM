from typing import AsyncIterator

import anthropic

from .interface import LLMProvider
from .tracing import get_langfuse


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
        force_tool: str | None = None,
    ) -> dict:
        claude_tools = []
        for t in tools:
            params = t["parameters"]
            if "properties" in params:
                input_schema = params
            else:
                input_schema = {
                    "type": "object",
                    "properties": {k: {"type": v} for k, v in params.items()},
                    "required": list(params.keys()),
                }
            claude_tools.append({
                "name": t["name"],
                "description": t["description"],
                "input_schema": input_schema,
            })

        kwargs: dict = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": messages,
        }
        if claude_tools:
            kwargs["tools"] = claude_tools
            if force_tool:
                # intent가 확정된 경우 해당 툴 반드시 호출
                kwargs["tool_choice"] = {"type": "tool", "name": force_tool}
            else:
                kwargs["tool_choice"] = {"type": "auto"}

        lf = get_langfuse()
        generation = None
        if lf:
            generation = lf.generation(
                name="claude_function_call",
                model=self.model,
                input=messages,
                metadata={"tools": [t["name"] for t in tools]},
            )

        try:
            response = await self.client.messages.create(**kwargs)

            result: dict
            for block in response.content:
                if block.type == "tool_use":
                    result = {
                        "type": "function_call",
                        "name": block.name,
                        "arguments": block.input,
                    }
                    break
            else:
                text = next((b.text for b in response.content if b.type == "text"), "")
                result = {"type": "text", "content": text}

            if generation:
                generation.end(
                    output=result,
                    usage={
                        "input": response.usage.input_tokens,
                        "output": response.usage.output_tokens,
                        "unit": "TOKENS",
                    },
                )
            return result

        except Exception as exc:
            if generation:
                generation.end(level="ERROR", status_message=str(exc))
            raise

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        lf = get_langfuse()
        generation = None
        if lf:
            generation = lf.generation(
                name="claude_stream",
                model=self.model,
                input=messages,
            )

        full_output: list[str] = []
        try:
            async with self.client.messages.stream(
                model=self.model,
                max_tokens=1024,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    full_output.append(text)
                    yield text
        finally:
            if generation:
                generation.end(output="".join(full_output))
