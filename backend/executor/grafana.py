import httpx

# LLM이 보내는 다양한 dashboard_type 표현 → 정규 키
_DASHBOARD_TYPE_ALIAS: dict[str, str] = {
    "node": "node",
    "node_exporter": "node",
    "node-exporter": "node",
    "nodeexporter": "node",
    "ec2": "node",
    "system": "node",
    "host": "node",
    "서버": "node",
    "시스템": "node",
    "인프라": "node",
    "service": "service",
    "app": "service",
    "application": "service",
    "jvm": "service",
    "spring": "service",
    "서비스": "service",
    "observability": "service",
}


def _normalize_dashboard_type(raw: str) -> str:
    lower = raw.lower().strip()
    if lower in _DASHBOARD_TYPE_ALIAS:
        return _DASHBOARD_TYPE_ALIAS[lower]
    for alias, canonical in _DASHBOARD_TYPE_ALIAS.items():
        if alias in lower:
            return canonical
    return "service"


def _service_panels(svc: str) -> list[dict]:
    """OTel Java Agent 메트릭 기반 패널 (exported_job 레이블로 서비스 필터)."""
    job = f'exported_job="{svc}"'
    return [
        {
            "type": "timeseries",
            "title": "Request Rate (rps)",
            "gridPos": {"h": 8, "w": 8, "x": 0, "y": 0},
            "targets": [{
                "expr": f'sum by(http_route, http_request_method) (rate(otel_http_server_request_duration_seconds_count{{{job}}}[5m]))',
                "legendFormat": "{{http_request_method}} {{http_route}}",
            }],
        },
        {
            "type": "timeseries",
            "title": "Error Rate (4xx+5xx)",
            "gridPos": {"h": 8, "w": 8, "x": 8, "y": 0},
            "targets": [{
                "expr": f'sum(rate(otel_http_server_request_duration_seconds_count{{{job},http_response_status_code=~"[45].."}}[5m]))',
                "legendFormat": "error rate",
            }],
        },
        {
            "type": "timeseries",
            "title": "Latency p99 (ms)",
            "gridPos": {"h": 8, "w": 8, "x": 16, "y": 0},
            "targets": [{
                "expr": f'histogram_quantile(0.99, sum by(le) (rate(otel_http_server_request_duration_seconds_bucket{{{job}}}[5m]))) * 1000',
                "legendFormat": "p99",
            }],
        },
        {
            "type": "timeseries",
            "title": "JVM CPU Utilization",
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
            "targets": [{
                "expr": f'otel_jvm_cpu_recent_utilization_ratio{{{job}}} * 100',
                "legendFormat": "CPU %",
            }],
        },
        {
            "type": "timeseries",
            "title": "JVM Heap Memory (MB)",
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
            "targets": [{
                "expr": f'otel_jvm_memory_used_bytes{{{job},jvm_memory_type="heap"}} / 1048576',
                "legendFormat": "heap used MB",
            }],
        },
        {
            "type": "timeseries",
            "title": "JVM Thread Count",
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 16},
            "targets": [{
                "expr": f'otel_jvm_thread_count{{{job}}}',
                "legendFormat": "threads ({{jvm_thread_state}})",
            }],
        },
        {
            "type": "timeseries",
            "title": "DB Connection Pool",
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 16},
            "targets": [{
                "expr": f'otel_db_client_connections_usage{{{job}}}',
                "legendFormat": "{{state}} {{pool_name}}",
            }],
        },
    ]


def _host_panels() -> list[dict]:
    """OTel hostmetrics receiver 기반 EC2 시스템 메트릭 패널.
    service.name=ec2-host 로 push된 데이터를 사용."""
    svc = 'exported_job="ec2-host"'
    return [
        {
            "type": "timeseries",
            "title": "CPU Utilization (%)",
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
            "targets": [{
                "expr": f'avg(otel_system_cpu_utilization_ratio{{{svc},state="user"}}) * 100',
                "legendFormat": "user",
            }, {
                "expr": f'avg(otel_system_cpu_utilization_ratio{{{svc},state="system"}}) * 100',
                "legendFormat": "system",
            }],
        },
        {
            "type": "timeseries",
            "title": "Memory Utilization (%)",
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
            "targets": [{
                "expr": f'otel_system_memory_utilization_ratio{{{svc},state="used"}} * 100',
                "legendFormat": "used %",
            }],
        },
        {
            "type": "timeseries",
            "title": "Disk I/O (bytes/s)",
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
            "targets": [{
                "expr": f'rate(otel_system_disk_io_bytes_total{{{svc},direction="read"}}[1m])',
                "legendFormat": "read {{device}}",
            }, {
                "expr": f'rate(otel_system_disk_io_bytes_total{{{svc},direction="write"}}[1m])',
                "legendFormat": "write {{device}}",
            }],
        },
        {
            "type": "timeseries",
            "title": "Network I/O (bytes/s)",
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
            "targets": [{
                "expr": f'rate(otel_system_network_io_bytes_total{{{svc},direction="receive"}}[1m])',
                "legendFormat": "rx {{device}}",
            }, {
                "expr": f'rate(otel_system_network_io_bytes_total{{{svc},direction="transmit"}}[1m])',
                "legendFormat": "tx {{device}}",
            }],
        },
        {
            "type": "timeseries",
            "title": "System Load Average",
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 16},
            "targets": [{
                "expr": f'otel_system_cpu_load_average_1m{{{svc}}}',
                "legendFormat": "load 1m",
            }, {
                "expr": f'otel_system_cpu_load_average_5m{{{svc}}}',
                "legendFormat": "load 5m",
            }],
        },
        {
            "type": "timeseries",
            "title": "Filesystem Utilization (%)",
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 16},
            "targets": [{
                "expr": f'otel_system_filesystem_utilization_ratio{{{svc}}} * 100',
                "legendFormat": "{{mountpoint}}",
            }],
        },
    ]


class GrafanaExecutor:
    def __init__(
        self,
        base_url: str,
        user: str = "admin",
        password: str = "admin123",
        prometheus_url: str = "",
    ):
        self.base_url = base_url.rstrip("/")
        self.auth = (user, password)
        self.prometheus_url = prometheus_url.rstrip("/")

    async def _prometheus_instant(self, client: httpx.AsyncClient, expr: str) -> list:
        """PromQL instant query 결과 반환. Prometheus 없으면 빈 리스트."""
        if not self.prometheus_url:
            return []
        try:
            resp = await client.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": expr},
                timeout=5.0,
            )
            data = resp.json()
            return data.get("data", {}).get("result", [])
        except Exception:
            return []

    async def _discover_metric(self, client: httpx.AsyncClient, keywords: list[str]) -> str | None:
        """panel_title 키워드로 Prometheus 메트릭명 검색, PromQL 스니펫 반환."""
        if not self.prometheus_url:
            return None
        try:
            resp = await client.get(
                f"{self.prometheus_url}/api/v1/label/__name__/values",
                timeout=5.0,
            )
            all_metrics: list[str] = resp.json().get("data", [])
        except Exception:
            return None

        # 키워드가 하나라도 포함된 메트릭만 필터
        lower_kws = [k.lower() for k in keywords]
        candidates = [m for m in all_metrics if any(kw in m.lower() for kw in lower_kws)]
        if not candidates:
            return None

        # _total 이면 rate(), bucket 이면 histogram_quantile, 아니면 그대로
        best = candidates[0]
        if best.endswith("_total"):
            return f'rate({best}{{}}[1m])'
        if "bucket" in best:
            return f'histogram_quantile(0.99, rate({best}{{}}[5m]))'
        return best

    async def _validate_and_fix_expr(
        self,
        client: httpx.AsyncClient,
        metric_expr: str,
        panel_title: str,
    ) -> tuple[str, str | None]:
        """PromQL 검증 후 데이터 없으면 자동 보정.
        Returns (final_expr, warning_message_or_None)"""
        result = await self._prometheus_instant(client, metric_expr)
        if result:
            return metric_expr, None  # 이미 정상

        # 빈 결과 → panel_title 키워드로 메트릭 탐색
        import re
        keywords = re.findall(r"[a-zA-Z가-힣]+", panel_title)
        # 영어 키워드 우선 (한글은 prometheus 메트릭명에 없음)
        en_kws = [w for w in keywords if w.isascii()] or keywords
        discovered = await self._discover_metric(client, en_kws)
        if discovered:
            # 발견된 메트릭으로 재검증
            result2 = await self._prometheus_instant(client, discovered)
            if result2:
                warn = f"입력한 쿼리에 데이터가 없어 '{discovered}'로 자동 보정했습니다."
                return discovered, warn

        return metric_expr, f"⚠️ 쿼리 '{metric_expr}'에 데이터가 없습니다. PromQL을 확인하세요."

    async def import_dashboard(self, dashboard_type: str, service_name: str) -> dict:
        normalized_type = _normalize_dashboard_type(dashboard_type)
        if normalized_type == "node":
            panels = _host_panels()
            title = "EC2 Host Metrics"
            service_name = service_name or "ec2-host"
        else:
            panels = _service_panels(service_name)
            title = "Service Overview"

        payload = {
            "dashboard": {
                "title": f"{service_name} - {title}",
                "uid": None,
                "version": 1,
                "schemaVersion": 38,
                "tags": [service_name, dashboard_type],
                "panels": panels,
                "time": {"from": "now-6h", "to": "now"},
                "refresh": "30s",
            },
            "overwrite": True,
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

    async def _find_dashboard(self, client: httpx.AsyncClient, name: str) -> dict | None:
        """이름으로 대시보드 검색 후 상세 정보 반환."""
        resp = await client.get(
            f"{self.base_url}/api/search",
            params={"query": name, "type": "dash-db"},
            auth=self.auth,
        )
        resp.raise_for_status()
        results = resp.json()
        if not results:
            return None
        uid = results[0]["uid"]
        detail = await client.get(
            f"{self.base_url}/api/dashboards/uid/{uid}",
            auth=self.auth,
        )
        detail.raise_for_status()
        return detail.json()

    async def modify_dashboard(
        self,
        action: str,
        dashboard_name: str,
        panel_title: str,
        metric_expr: str | None = None,
        legend: str | None = None,
    ) -> dict:
        async with httpx.AsyncClient(timeout=15.0) as client:
            found = await self._find_dashboard(client, dashboard_name)
            if not found:
                return {
                    "status": "error",
                    "message": f"대시보드를 찾을 수 없습니다: '{dashboard_name}'",
                }

            db = found["dashboard"]
            panels: list[dict] = db.get("panels", [])
            meta = found["meta"]

            if action == "remove":
                original_count = len(panels)
                panels = [p for p in panels if p.get("title", "").lower() != panel_title.lower()]
                removed = original_count - len(panels)
                if removed == 0:
                    return {
                        "status": "error",
                        "message": f"패널 '{panel_title}'을 찾을 수 없습니다.",
                    }
                msg = f"패널 삭제 완료: '{panel_title}'"

            elif action == "add":
                if not metric_expr:
                    return {"status": "error", "message": "패널 추가 시 metric_expr(PromQL)이 필요합니다."}
                # PromQL 검증 및 자동 보정
                final_expr, warn = await self._validate_and_fix_expr(client, metric_expr, panel_title)
                # 기존 패널 최하단 y 좌표 계산
                max_y = max((p.get("gridPos", {}).get("y", 0) + p.get("gridPos", {}).get("h", 8) for p in panels), default=0)
                new_panel = {
                    "type": "timeseries",
                    "title": panel_title,
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": max_y},
                    "targets": [{
                        "expr": final_expr,
                        "legendFormat": legend or "{{device}} {{direction}}",
                    }],
                }
                panels.append(new_panel)
                msg = f"패널 추가 완료: '{panel_title}' (쿼리: `{final_expr}`)"
                if warn:
                    msg += f"\n{warn}"
            else:
                return {"status": "error", "message": f"지원하지 않는 action: {action}"}

            db["panels"] = panels
            db["version"] = db.get("version", 1) + 1

            resp = await client.post(
                f"{self.base_url}/api/dashboards/db",
                json={"dashboard": db, "overwrite": True, "folderId": meta.get("folderId", 0)},
                auth=self.auth,
            )
            resp.raise_for_status()
            result = resp.json()

        return {
            "status": "success",
            "dashboard_url": f"{self.base_url}{result.get('url', '')}",
            "message": msg,
        }
