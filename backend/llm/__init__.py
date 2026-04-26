import os

import yaml

from .interface import LLMProvider


def get_provider(config_path: str | None = None) -> LLMProvider:
    """config.yml 기반으로 LLM Provider 인스턴스 반환"""
    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), "..", "config.yml")

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    llm_cfg = config["llm"]
    provider = llm_cfg["provider"]
    model = llm_cfg["model"]

    if provider == "openai":
        from .openai_provider import OpenAIProvider
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY가 설정되지 않았습니다. backend 실행 환경에 OPENAI_API_KEY를 설정하세요."
            )
        return OpenAIProvider(model=model, api_key=api_key)

    if provider == "claude":
        from .claude_provider import ClaudeProvider
        return ClaudeProvider(model=model, api_key=os.getenv("ANTHROPIC_API_KEY"))

    if provider == "ollama":
        from .ollama_provider import OllamaProvider
        return OllamaProvider(
            model=model,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )

    raise ValueError(f"Unknown LLM provider: {provider}")
