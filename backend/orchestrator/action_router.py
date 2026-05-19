from fastapi import HTTPException

from intent.classifier import ClassifiedIntent, IntentType

# 허용된 Action 정의 (Function Calling 툴 목록)
TOOLS: list[dict] = [
    {
        "name": "create_monitoring_target",
        "description": (
            "모니터링 대상 추가. 로컬 서비스(Prometheus Pull)와 "
            "AWS 외부 서비스(EC2/ECS/Lambda, OTel Push) 모두 지원. "
            "AWS 서비스는 ngrok 터널 URL과 연동 가이드를 자동 생성한다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "서비스 이름 (예: order-service, user-api)",
                },
                "service_type": {
                    "type": "string",
                    "enum": ["local", "aws-ec2", "aws-ecs", "aws-lambda"],
                    "description": "서비스 배포 환경",
                },
                "endpoint": {
                    "type": "string",
                    "description": (
                        "local 전용: Prometheus 스크레이프 URL (예: http://host:port/metrics). "
                        "aws 서비스는 ngrok URL이 자동 설정되므로 생략 가능."
                    ),
                },
                "environment": {
                    "type": "string",
                    "enum": ["dev", "staging", "production"],
                    "description": "배포 환경 구분",
                },
                "integration_method": {
                    "type": "string",
                    "enum": ["otel-sdk", "fluent-bit", "prometheus-exporter"],
                    "description": "연동 방식 (생략 시 otel-sdk 기본값)",
                },
            },
            "required": ["service_name", "service_type", "environment"],
        },
    },
    {
        "name": "create_alert_rule",
        "description": "Prometheus + Alertmanager에 알림 규칙 생성",
        "parameters": {
            "metric": "string",
            "threshold": "number",
            "duration": "string",
            "severity": "string",
        },
    },
    {
        "name": "import_dashboard",
        "description": "Grafana 대시보드 신규 생성. dashboard_type: 'service'(JVM/HTTP 앱) 또는 'node'(EC2 시스템)",
        "parameters": {
            "dashboard_type": "string",
            "service_name": "string",
        },
    },
    {
        "name": "modify_dashboard",
        "description": (
            "기존 Grafana 대시보드에 패널 추가(add) 또는 삭제(remove). "
            "모든 OTel 메트릭은 'otel_' 접두사를 가지며 exported_job 레이블로 서비스를 구분한다. "
            "EC2 호스트 메트릭은 exported_job=\"ec2-host\", 앱 메트릭은 exported_job=\"magambell-dev\" 사용. "
            "metric_expr PromQL 예시:\n"
            "- EC2 Disk IOPS: rate(otel_system_disk_operations_total{exported_job=\"ec2-host\",device=\"xvda\"}[1m])\n"
            "- EC2 Disk Throughput: rate(otel_system_disk_io_bytes_total{exported_job=\"ec2-host\",device=\"xvda\"}[1m])\n"
            "- EC2 CPU: avg(otel_system_cpu_utilization_ratio{exported_job=\"ec2-host\",state=\"user\"}) * 100\n"
            "- EC2 Memory: otel_system_memory_utilization_ratio{exported_job=\"ec2-host\",state=\"used\"} * 100\n"
            "- EC2 Network RX: rate(otel_system_network_io_bytes_total{exported_job=\"ec2-host\",direction=\"receive\"}[1m])\n"
            "- App Request Rate: rate(otel_http_server_request_duration_seconds_count{exported_job=\"magambell-dev\"}[5m])\n"
            "- App Latency p99: histogram_quantile(0.99, rate(otel_http_server_request_duration_seconds_bucket{exported_job=\"magambell-dev\"}[5m])) * 1000\n"
            "- JVM GC Rate: rate(otel_jvm_gc_duration_seconds_count{exported_job=\"magambell-dev\"}[5m])\n"
            "- JVM Heap: otel_jvm_memory_used_bytes{exported_job=\"magambell-dev\",jvm_memory_type=\"heap\"} / 1048576\n"
            "- JVM Threads: otel_jvm_thread_count{exported_job=\"magambell-dev\"}\n"
            "- DB Connection Pool: otel_db_client_connections_usage{exported_job=\"magambell-dev\"}"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "remove"],
                    "description": "add: 패널 추가, remove: 패널 삭제",
                },
                "dashboard_name": {
                    "type": "string",
                    "description": "수정할 대시보드 이름 (부분 일치 검색)",
                },
                "panel_title": {
                    "type": "string",
                    "description": "추가하거나 삭제할 패널 제목",
                },
                "metric_expr": {
                    "type": "string",
                    "description": "추가 시 사용할 PromQL 표현식 (add 전용)",
                },
                "legend": {
                    "type": "string",
                    "description": "추가 시 범례 형식 (add 전용, 예: {{http_route}})",
                },
            },
            "required": ["action", "dashboard_name", "panel_title"],
        },
    },
    {
        "name": "search_logs",
        "description": "Elasticsearch에서 로그 검색",
        "parameters": {
            "level": "string",
            "service": "string",
            "time_range": "string",
            "group_by": "string",
        },
    },
    {
        "name": "summarize_alerts",
        "description": "최근 알림 현황 요약",
        "parameters": {
            "time_range": "string",
            "service": "string",
        },
    },
    {
        "name": "list_monitoring_targets",
        "description": "현재 Prometheus에 등록된 모니터링 대상 목록과 UP/DOWN 상태 조회. '연동된 서비스 목록', '모니터링 중인 서비스', '현황' 등의 요청에 사용.",
        "parameters": {
            "service_filter": "string",
        },
    },
]

_TOOLS_BY_NAME: dict[str, dict] = {t["name"]: t for t in TOOLS}
ALLOWED_ACTIONS: frozenset[str] = frozenset(_TOOLS_BY_NAME.keys())

_INTENT_TO_TOOL: dict[IntentType, str] = {
    IntentType.CREATE_MONITORING_TARGET: "create_monitoring_target",
    IntentType.CREATE_ALERT_RULE: "create_alert_rule",
    IntentType.IMPORT_DASHBOARD: "import_dashboard",
    IntentType.MODIFY_DASHBOARD: "modify_dashboard",
    IntentType.SEARCH_LOGS: "search_logs",
    IntentType.SUMMARIZE_ALERTS: "summarize_alerts",
    IntentType.LIST_MONITORING_TARGETS: "list_monitoring_targets",
}


def get_tools_for_intent(intent: ClassifiedIntent) -> list[dict]:
    """Intent에 대응하는 허용된 툴 반환. UNKNOWN이면 400, 미허용이면 403."""
    if intent.intent == IntentType.UNKNOWN:
        raise HTTPException(status_code=400, detail="인식할 수 없는 요청입니다.")

    tool_name = _INTENT_TO_TOOL.get(intent.intent)
    if not tool_name or tool_name not in ALLOWED_ACTIONS:
        raise HTTPException(status_code=403, detail=f"허용되지 않은 액션: {tool_name}")

    return [_TOOLS_BY_NAME[tool_name]]


def validate_action(action_name: str) -> bool:
    return action_name in ALLOWED_ACTIONS
