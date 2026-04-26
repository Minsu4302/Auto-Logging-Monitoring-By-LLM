from llm.interface import LLMProvider


class LLMAnalyzer:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def analyze_logs(self, logs: list[dict], query: str) -> str:
        if not logs:
            return "분석할 로그가 없습니다."

        log_sample = logs[:20]
        log_text = "\n".join(str(log) for log in log_sample)

        messages = [
            {
                "role": "user",
                "content": (
                    "당신은 시스템 로그 분석 전문가입니다. "
                    "로그 데이터를 분석하여 핵심 패턴, 에러, 이상 징후를 한국어로 요약해주세요.\n\n"
                    f"질문: {query}\n\n"
                    f"로그 샘플 (전체 {len(logs)}건 중 최대 20건):\n{log_text}"
                ),
            }
        ]

        chunks: list[str] = []
        async for chunk in self.llm.stream(messages):
            chunks.append(chunk)
        return "".join(chunks)

    async def summarize_alerts(self, alert_data: dict, query: str) -> str:
        messages = [
            {
                "role": "user",
                "content": (
                    "당신은 시스템 모니터링 전문가입니다. "
                    "알림 현황을 분석하여 운영자가 즉시 이해할 수 있는 요약을 한국어로 작성해주세요.\n\n"
                    f"질문: {query}\n\n"
                    f"알림 현황:\n{alert_data}"
                ),
            }
        ]

        chunks: list[str] = []
        async for chunk in self.llm.stream(messages):
            chunks.append(chunk)
        return "".join(chunks)

    async def analyze_failure(self, context: dict) -> str:
        messages = [
            {
                "role": "user",
                "content": (
                    "당신은 SRE 전문가입니다. "
                    "장애 컨텍스트를 분석하여 근본 원인(Root Cause)과 해결 방안을 한국어로 제시해주세요.\n\n"
                    f"장애 컨텍스트:\n{context}"
                ),
            }
        ]

        chunks: list[str] = []
        async for chunk in self.llm.stream(messages):
            chunks.append(chunk)
        return "".join(chunks)
