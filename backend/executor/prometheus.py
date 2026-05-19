import httpx


class PrometheusExecutor:
    def __init__(self, base_url: str, read_only: bool = False):
        self.base_url = base_url.rstrip("/")
        self.read_only = read_only

    async def add_scrape_target(self, host: str, port: int, job_name: str) -> dict:
        """
        Prometheus scrape 대상 추가.
        read_only=True (prod 환경)이면 /-/reload를 호출하지 않고
        운영자가 직접 적용해야 할 설정 가이드만 반환한다.
        """
        if self.read_only:
            return {
                "status": "readonly",
                "job_name": job_name,
                "target": f"{host}:{port}",
                "message": (
                    f"[Prod 읽기 전용] Prometheus 설정 변경이 차단되었습니다.\n\n"
                    f"아래 설정을 EC2의 prometheus.yml에 직접 추가한 후 Prometheus를 재시작하세요:\n\n"
                    f"```yaml\n"
                    f"- job_name: '{job_name}'\n"
                    f"  static_configs:\n"
                    f"    - targets: ['{host}:{port}']\n"
                    f"```\n\n"
                    f"적용 명령: `sudo systemctl reload prometheus` 또는 `curl -X POST http://localhost:9090/-/reload`"
                ),
            }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self.base_url}/api/v1/status/config")
            resp.raise_for_status()

        # /-/reload 는 --web.enable-lifecycle 옵션 필요
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
