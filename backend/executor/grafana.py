import httpx

_DASHBOARD_TEMPLATES: dict[str, dict] = {
    "node": {
        "title": "Node Exporter",
        "panels": [
            {
                "type": "timeseries",
                "title": "CPU Usage %",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
                "targets": [{"expr": "100 - (avg by(instance)(rate(node_cpu_seconds_total{mode='idle'}[5m])) * 100)", "legendFormat": "{{instance}}"}],
            },
            {
                "type": "timeseries",
                "title": "Memory Usage",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
                "targets": [{"expr": "node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes", "legendFormat": "{{instance}}"}],
            },
        ],
    },
    "service": {
        "title": "Service Overview",
        "panels": [
            {
                "type": "timeseries",
                "title": "Request Rate (rps)",
                "gridPos": {"h": 8, "w": 8, "x": 0, "y": 0},
                "targets": [{"expr": "rate(http_requests_total[5m])", "legendFormat": "{{method}} {{path}}"}],
            },
            {
                "type": "timeseries",
                "title": "Error Rate",
                "gridPos": {"h": 8, "w": 8, "x": 8, "y": 0},
                "targets": [{"expr": "rate(http_requests_total{status=~'5..'}[5m])", "legendFormat": "5xx"}],
            },
            {
                "type": "timeseries",
                "title": "Latency p99",
                "gridPos": {"h": 8, "w": 8, "x": 16, "y": 0},
                "targets": [{"expr": "histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))", "legendFormat": "p99"}],
            },
        ],
    },
}


class GrafanaExecutor:
    def __init__(
        self,
        base_url: str,
        user: str = "admin",
        password: str = "admin123",
    ):
        self.base_url = base_url.rstrip("/")
        self.auth = (user, password)

    async def import_dashboard(self, dashboard_type: str, service_name: str) -> dict:
        template = _DASHBOARD_TEMPLATES.get(
            dashboard_type, _DASHBOARD_TEMPLATES["service"]
        )
        payload = {
            "dashboard": {
                **template,
                "title": f"{service_name} - {template['title']}",
                "uid": None,
                "version": 1,
                "schemaVersion": 38,
                "tags": [service_name, dashboard_type],
            },
            "overwrite": False,
            "folderId": 0,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/dashboards/db",
                json=payload,
                auth=self.auth,
            )
            resp.raise_for_status()
            result = resp.json()

        return {
            "status": "success",
            "uid": result.get("uid"),
            "dashboard_url": f"{self.base_url}{result.get('url', '')}",
            "message": f"대시보드 생성 완료: {service_name} ({dashboard_type})",
        }
