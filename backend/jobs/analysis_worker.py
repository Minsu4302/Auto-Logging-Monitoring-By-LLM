import json
import os

from arq.connections import RedisSettings
import yaml


async def analyze_logs_job(ctx: dict, job_id: str, query: str, log_params: dict) -> dict:
    """ARQ Worker: 무거운 로그 분석 비동기 처리"""
    from analyzer.llm_analyzer import LLMAnalyzer
    from executor.elasticsearch import ElasticsearchExecutor
    from llm import get_provider

    redis = ctx["redis"]

    # 처리 시작 상태 기록
    await redis.setex(f"job:{job_id}:status", 3600, "processing")

    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yml")
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    es_url = cfg["services"]["elasticsearch_url"]
    llm = get_provider(config_path)
    es = ElasticsearchExecutor(es_url)

    log_data = await es.search_logs(**log_params)
    analyzer = LLMAnalyzer(llm)
    result_text = await analyzer.analyze_logs(log_data.get("logs", []), query)

    # 결과 및 완료 상태 기록
    await redis.setex(f"job:{job_id}:result", 3600, json.dumps(result_text, ensure_ascii=False))
    await redis.setex(f"job:{job_id}:status", 3600, "completed")

    return {"job_id": job_id, "status": "completed"}


class WorkerSettings:
    functions = [analyze_logs_job]
    max_jobs = 10
    job_timeout = 300


def _load_config() -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "config.yml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_redis_settings() -> RedisSettings:
    env_host = os.getenv("REDIS_HOST")
    env_port = os.getenv("REDIS_PORT")
    if env_host or env_port:
        return RedisSettings(
            host=env_host or "redis",
            port=int(env_port or "6379"),
        )

    cfg = _load_config()
    redis_url = cfg["services"]["redis_url"]
    without_scheme = redis_url.replace("redis://", "")
    host, _, port_str = without_scheme.partition(":")
    return RedisSettings(host=host, port=int(port_str or 6379))


WorkerSettings.redis_settings = _get_redis_settings()
