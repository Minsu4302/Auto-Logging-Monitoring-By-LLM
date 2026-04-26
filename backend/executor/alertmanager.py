import httpx


class AlertmanagerExecutor:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def get_alerts(
        self,
        time_range: str = "1h",
        service: str | None = None,
    ) -> dict:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self.base_url}/api/v2/alerts",
                params={"active": "true", "silenced": "false"},
            )
            resp.raise_for_status()
            alerts: list[dict] = resp.json()

        if service:
            alerts = [
                a for a in alerts
                if service in str(a.get("labels", {}))
            ]

        def severity(a: dict) -> str:
            return a.get("labels", {}).get("severity", "unknown")

        return {
            "total": len(alerts),
            "critical": sum(1 for a in alerts if severity(a) == "critical"),
            "warning": sum(1 for a in alerts if severity(a) == "warning"),
            "time_range": time_range,
            "alerts": [
                {
                    "name": a.get("labels", {}).get("alertname"),
                    "severity": severity(a),
                    "summary": a.get("annotations", {}).get("summary"),
                    "started_at": a.get("startsAt"),
                }
                for a in alerts[:10]
            ],
        }
