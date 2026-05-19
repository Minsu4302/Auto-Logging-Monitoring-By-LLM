from datetime import datetime, timedelta

import httpx

_TIME_RANGE_MAP: dict[str, timedelta] = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}

# LLM이 보내는 다양한 time_range 표현 → 정규 키
_TIME_RANGE_ALIAS: dict[str, str] = {
    "last_1_hour": "1h",
    "last1hour": "1h",
    "1 hour": "1h",
    "last_6_hours": "6h",
    "last_24_hours": "24h",
    "last24hours": "24h",
    "24 hours": "24h",
    "1 day": "24h",
    "today": "24h",
    "last_7_days": "7d",
    "7 days": "7d",
    "1 week": "7d",
    "일주일": "7d",
    "하루": "24h",
    "오늘": "24h",
    "한시간": "1h",
}

# Korean/alias → OTel SeverityText canonical value
_LEVEL_ALIAS: dict[str, str] = {
    "경고": "WARN",
    "warning": "WARN",
    "warn": "WARN",
    "에러": "ERROR",
    "오류": "ERROR",
    "error": "ERROR",
    "err": "ERROR",
    "정보": "INFO",
    "information": "INFO",
    "info": "INFO",
    "debug": "DEBUG",
    "디버그": "DEBUG",
    "fatal": "FATAL",
    "critical": "FATAL",
}

# service 값이 "전체"/"all" 등이면 필터 제거
_SERVICE_SKIP = {"all", "all services", "전체", "모든", "모든 서비스", "none", "any"}


def _normalize_level(level: str) -> str:
    lower = level.lower()
    if lower in _LEVEL_ALIAS:
        return _LEVEL_ALIAS[lower]
    for alias, canonical in _LEVEL_ALIAS.items():
        if alias in lower:
            return canonical
    return level.upper()


def _normalize_time_range(time_range: str) -> str:
    lower = time_range.lower().strip()
    if lower in _TIME_RANGE_MAP:
        return lower
    if lower in _TIME_RANGE_ALIAS:
        return _TIME_RANGE_ALIAS[lower]
    for alias, canonical in _TIME_RANGE_ALIAS.items():
        if alias in lower:
            return canonical
    return "24h"  # unknown → 24h로 넓게


class ElasticsearchExecutor:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def search_logs(
        self,
        level: str | None = None,
        service: str | None = None,
        time_range: str = "1h",
        group_by: str | None = None,
        size: int = 100,
    ) -> dict:
        if not self.base_url:
            return {
                "total": 0,
                "logs": [],
                "aggregations": {},
                "message": (
                    "Elasticsearch가 이 환경에 설치되어 있지 않습니다.\n"
                    "로그 수집을 원한다면 EC2에 Fluent Bit + Elasticsearch를 추가하거나 "
                    "CloudWatch Logs를 연동하세요."
                ),
            }

        canonical_range = _normalize_time_range(time_range)
        delta = _TIME_RANGE_MAP.get(canonical_range, timedelta(hours=24))
        gte = (datetime.utcnow() - delta).isoformat() + "Z"

        must: list[dict] = [
            {"range": {"@timestamp": {"gte": gte, "lte": "now"}}}
        ]
        if level:
            normalized_level = _normalize_level(level)
            must.append({"term": {"SeverityText.keyword": normalized_level}})
        if service and service.lower().strip() not in _SERVICE_SKIP:
            must.append({"term": {"Resource.service.name.keyword": service}})

        body: dict = {
            "query": {"bool": {"must": must}},
            "sort": [{"@timestamp": {"order": "desc"}}],
            "size": size,
        }
        if group_by:
            agg_field = group_by if "." in group_by else f"{group_by}.keyword"
            body["aggs"] = {"group": {"terms": {"field": agg_field, "size": 20}}}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/*logs*/_search",
                json=body,
                headers={"Content-Type": "application/json"},
                params={
                    "ignore_unavailable": "true",
                    "allow_no_indices": "true",
                },
            )
            resp.raise_for_status()
            result = resp.json()

        hits = result.get("hits", {}).get("hits", [])
        total = result.get("hits", {}).get("total", {}).get("value", 0)

        return {
            "total": total,
            "logs": [h.get("_source", {}) for h in hits],
            "aggregations": result.get("aggregations", {}),
        }
