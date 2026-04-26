from abc import ABC, abstractmethod
from typing import AsyncIterator


class LLMProvider(ABC):
    @abstractmethod
    async def function_call(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> dict:
        """Function Calling 실행. 반환: {"type": "function_call"|"text", ...}"""
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
