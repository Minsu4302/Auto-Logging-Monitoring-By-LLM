from abc import ABC, abstractmethod
from typing import AsyncIterator


class LLMProvider(ABC):
    @abstractmethod
    async def function_call(
        self,
        messages: list[dict],
        tools: list[dict],
        force_tool: str | None = None,
    ) -> dict:
        """
        Function Calling 실행. 반환: {"type": "function_call"|"text", ...}
        force_tool: 툴 이름을 지정하면 LLM이 반드시 해당 툴을 호출 (tool_choice 강제).
        Intent가 확정된 경우 LLM이 임의로 텍스트 응답하는 것을 방지한다.
        """
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[dict],
    ) -> AsyncIterator[str]:
        """텍스트 스트리밍 응답"""
        ...

    async def complete(self, messages: list[dict]) -> str:
        """스트리밍을 모아 단일 문자열로 반환 (분류·분석용)"""
        chunks: list[str] = []
        async for chunk in self.stream(messages):
            chunks.append(chunk)
        return "".join(chunks)
