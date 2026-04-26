import json
import os

from arq.connections import RedisSettings


async def analyze_logs_job(ctx: dict, job_id: str, query: str, log_params: dict) -> dict:
    """ARQ Worker: 무거운 로그 분석 비동기 처리"""
    import yaml
    from analyzer.llm_analyzer import LLMAnalyzer
    from executor.elasticsearch import ElasticsearchExecutor
    from llm import get_provider

    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yml")
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    es_url = cfg["services"]["elasticsearch_url"]
    llm = get_provider(config_path)
    es = ElasticsearchExecutor(es_url)

    log_data = await es.search_logs(**log_params)
    analyzer = LLMAnalyzer(llm)
    result_text = await analyzer.analyze_logs(log_data.get("logs", []), query)

    redis = ctx["redis"]
    await redis.setex(f"job:{job_id}:result", 3600, json.dumps(result_text, ensure_ascii=False))
    return {"job_id": job_id, "status": "completed"}


class WorkerSettings:
    functions = [analyze_logs_job]
    redis_settings = RedisSettings(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", "6379")),
    )
    max_jobs = 10
    job_timeout = 300
