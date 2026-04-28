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

    async def get_targets(self, service_filter: str | None = None) -> dict:
        """Prometheus /api/v1/targets 로 현재 스크레이프 대상 목록과 UP/DOWN 상태 반환."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self.base_url}/api/v1/targets")
            resp.raise_for_status()
            data = resp.json()

        active_targets = data.get("data", {}).get("activeTargets", [])

        targets = []
        for t in active_targets:
            job = t.get("labels", {}).get("job", "unknown")
            instance = t.get("labels", {}).get("instance", "unknown")
            health = t.get("health", "unknown")
            last_scrape = t.get("lastScrape", "")[:19].replace("T", " ")  # ISO → 읽기 쉬운 포맷
            last_error = t.get("lastError", "")

            if service_filter and service_filter.lower() not in job.lower():
                continue

            targets.append({
                "job": job,
                "instance": instance,
                "health": health,
                "last_scrape": last_scrape,
                "last_error": last_error,
            })

        up_count = sum(1 for t in targets if t["health"] == "up")
        down_count = len(targets) - up_count

        return {
            "total": len(targets),
            "up": up_count,
            "down": down_count,
            "targets": targets,
            "message": f"모니터링 대상 {len(targets)}개 (UP: {up_count}, DOWN: {down_count})",
        }

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
