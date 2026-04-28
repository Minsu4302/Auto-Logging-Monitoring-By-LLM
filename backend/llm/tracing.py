import logging
import os

logger = logging.getLogger(__name__)

_langfuse = None
_initialized = False


def get_langfuse():
    """
    Langfuse 클라이언트 싱글톤 반환.
    LANGFUSE_PUBLIC_KEY / SECRET_KEY 가 미설정이면 None 반환 (트레이싱 비활성).
    """
    global _langfuse, _initialized
    if _initialized:
        return _langfuse

    _initialized = True
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
    host = os.getenv("LANGFUSE_HOST", "http://langfuse:3000")

    placeholder = ("pk-lf-...", "sk-lf-...")
    if not public_key or not secret_key or public_key in placeholder or secret_key in placeholder:
        logger.info("Langfuse 키 미설정 — 트레이싱 비활성화")
        return None

    try:
        from langfuse import Langfuse

        _langfuse = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
        logger.info("Langfuse 트레이싱 활성화 (host=%s)", host)
    except Exception as exc:
        logger.warning("Langfuse 초기화 실패 — 트레이싱 비활성화: %s", exc)

    return _langfuse
