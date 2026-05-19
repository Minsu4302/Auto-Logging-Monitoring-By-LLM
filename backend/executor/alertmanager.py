import httpx


class AlertmanagerExecutor:
    def __init__(self, base_url: str, prometheus_url: str = ""):
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.prometheus_url = prometheus_url.rstrip("/") if prometheus_url else ""

    async def get_alerts(
        self,
        time_range: str = "1h",
        service: str | None = None,
    ) -> dict:
        # Alertmanager URL이 없으면 Prometheus ALERTS 쿼리로 대체
        if not self.base_url:
            return await self._get_alerts_from_prometheus(time_range, service)

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
            "source": "alertmanager",
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

    async def _get_alerts_from_prometheus(
        self,
        time_range: str,
        service: str | None,
    ) -> dict:
        """Alertmanager 미설치 환경에서 Prometheus ALERTS 메트릭으로 대체."""
        if not self.prometheus_url:
            return {
                "total": 0,
                "critical": 0,
                "warning": 0,
                "time_range": time_range,
                "source": "unavailable",
                "alerts": [],
                "message": "Alertmanager와 Prometheus가 모두 설정되지 않았습니다.",
            }

        promql = 'ALERTS{alertstate="firing"}'
        if service:
            promql = f'ALERTS{{alertstate="firing", job=~".*{service}.*"}}'

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": promql},
            )
            resp.raise_for_status()
            data = resp.json()

        results = data.get("data", {}).get("result", [])

        def sev(m: dict) -> str:
            return m.get("severity", m.get("alertname", "unknown")).lower()

        alerts = [
            {
                "name": r["metric"].get("alertname", "unknown"),
                "severity": r["metric"].get("severity", "unknown"),
                "summary": r["metric"].get("alertname", ""),
                "started_at": None,
                "labels": r["metric"],
            }
            for r in results
        ]

        return {
            "total": len(alerts),
            "critical": sum(1 for a in alerts if a["severity"] == "critical"),
            "warning": sum(1 for a in alerts if a["severity"] == "warning"),
            "time_range": time_range,
            "source": "prometheus",
            "note": "Alertmanager 미설치 — Prometheus ALERTS{alertstate=\"firing\"} 기반 조회",
            "alerts": alerts[:10],
        }
