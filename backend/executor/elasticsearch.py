from datetime import datetime, timedelta

import httpx

_TIME_RANGE_MAP: dict[str, timedelta] = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}


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
        delta = _TIME_RANGE_MAP.get(time_range, timedelta(hours=1))
        gte = (datetime.utcnow() - delta).isoformat() + "Z"

        must: list[dict] = [
            {"range": {"@timestamp": {"gte": gte, "lte": "now"}}}
        ]
        if level:
            must.append({"term": {"level": level}})
        if service:
            must.append({"term": {"service.keyword": service}})

        body: dict = {
            "query": {"bool": {"must": must}},
            "sort": [{"@timestamp": {"order": "desc"}}],
            "size": size,
        }
        if group_by:
            body["aggs"] = {"group": {"terms": {"field": group_by, "size": 20}}}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/logs/_search",
                json=body,
                headers={"Content-Type": "application/json"},
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
