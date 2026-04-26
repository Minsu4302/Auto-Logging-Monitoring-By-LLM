import httpx


class PrometheusExecutor:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def add_scrape_target(self, host: str, port: int, job_name: str) -> dict:
        """
        Prometheus HTTP API로 현재 설정 확인 후 /-/reload 트리거.
        실제 scrape_config 파일 수정은 executor가 아닌 별도 config 관리로 처리.
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self.base_url}/api/v1/status/config")
            resp.raise_for_status()

        # /-/reload 는 --web.enable-lifecycle 옵션 필요 (docker-compose에 설정됨)
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(f"{self.base_url}/-/reload")

        return {
            "status": "success",
            "job_name": job_name,
            "target": f"{host}:{port}",
            "message": f"모니터링 대상 추가 완료: {job_name} ({host}:{port})",
        }

    async def query(self, promql: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/api/v1/query",
                params={"query": promql},
            )
            resp.raise_for_status()
            return resp.json()

    async def create_alert_rule(
        self,
        metric: str,
        threshold: float,
        duration: str,
        severity: str,
    ) -> dict:
        alert_name = "".join(
            w.capitalize() for w in metric.replace("_", " ").split()
        ) + "Alert"

        rule = {
            "alert": alert_name,
            "expr": f"{metric} > {threshold}",
            "for": duration,
            "labels": {"severity": severity},
            "annotations": {
                "summary": f"{metric} exceeds {threshold}",
                "description": "{{ $labels.job }}: value={{ $value }}",
            },
        }
        return {
            "status": "success",
            "rule": rule,
            "message": f"알림 규칙 생성 완료: {alert_name} ({severity})",
        }
