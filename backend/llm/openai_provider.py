import json
from typing import AsyncIterator

from openai import AsyncOpenAI

from .interface import LLMProvider
from .tracing import get_langfuse


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def function_call(
        self,
        messages: list[dict],
        tools: list[dict],
        force_tool: str | None = None,
    ) -> dict:
        openai_tools = []
        for t in tools:
            params = t["parameters"]
            # 이미 JSON Schema 형식이면 그대로, 아니면 flat dict에서 변환
            if "properties" in params:
                parameters_schema = params
            else:
                parameters_schema = {
                    "type": "object",
                    "properties": {k: {"type": v, "description": k} for k, v in params.items()},
                    "required": list(params.keys()),
                }
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": parameters_schema,
                },
            })

        kwargs: dict = {"model": self.model, "messages": messages}
        if openai_tools:
            kwargs["tools"] = openai_tools
            if force_tool:
                # intent가 확정된 경우 해당 툴 반드시 호출
                kwargs["tool_choice"] = {"type": "function", "function": {"name": force_tool}}
            else:
                kwargs["tool_choice"] = "auto"

        lf = get_langfuse()
        generation = None
        if lf:
            generation = lf.generation(
                name="openai_function_call",
                model=self.model,
                input=messages,
                metadata={"tools": [t["name"] for t in tools]},
            )

        try:
            response = await self.client.chat.completions.create(**kwargs)
            msg = response.choices[0].message

            if msg.tool_calls:
                tc = msg.tool_calls[0]
                result = {
                    "type": "function_call",
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                }
            else:
                result = {"type": "text", "content": msg.content or ""}

            if generation:
                generation.end(
                    output=result,
                    usage={
                        "input": response.usage.prompt_tokens,
                        "output": response.usage.completion_tokens,
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
                name="openai_stream",
                model=self.model,
                input=messages,
            )

        full_output: list[str] = []
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
            )
            async for chunk in response:
                delta = chunk.choices[0].delta.content
                if delta:
                    full_output.append(delta)
                    yield delta
        finally:
            if generation:
                generation.end(output="".join(full_output))
