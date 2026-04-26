import json
from typing import AsyncIterator

import httpx

from .interface import LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        model: str = "llama3",
        base_url: str = "http://localhost:11434",
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def function_call(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> dict:
        # Ollama는 네이티브 tool calling 미지원 → 프롬프트로 JSON 유도
        prompt = self._build_tool_prompt(messages, tools)
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
            )
            resp.raise_for_status()
            content: str = resp.json()["message"]["content"]

        try:
            parsed = json.loads(content)
            if "name" in parsed and "arguments" in parsed:
                return {
                    "type": "function_call",
                    "name": parsed["name"],
                    "arguments": parsed["arguments"],
                }
        except json.JSONDecodeError:
            pass
        return {"type": "text", "content": content}

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": messages, "stream": True},
            ) as response:
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        pass

    def _build_tool_prompt(self, messages: list[dict], tools: list[dict]) -> str:
        tools_json = json.dumps(tools, ensure_ascii=False, indent=2)
        last_user_msg = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
        )
        return (
            f"Available tools:\n{tools_json}\n\n"
            f"User request: {last_user_msg}\n\n"
            'Respond with ONLY valid JSON: {"name": "<tool_name>", "arguments": {...}}'
        )
