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
        "description": "Grafana 대시보드 생성",
        "parameters": {
            "dashboard_type": "string",
            "service_name": "string",
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
