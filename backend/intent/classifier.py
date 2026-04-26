import json
import re
from dataclasses import dataclass
from enum import Enum

from llm.interface import LLMProvider


class IntentType(str, Enum):
    CREATE_MONITORING_TARGET = "create_monitoring_target"
    CREATE_ALERT_RULE = "create_alert_rule"
    IMPORT_DASHBOARD = "import_dashboard"
    SEARCH_LOGS = "search_logs"
    SUMMARIZE_ALERTS = "summarize_alerts"
    UNKNOWN = "unknown"


@dataclass
class ClassifiedIntent:
    intent: IntentType
    confidence: float
    raw_query: str


_SYSTEM_PROMPT = """You are an intent classifier for an observability system.
Classify the user's request into exactly one of these intents:
- create_monitoring_target: Add a new service/host to monitor
- create_alert_rule: Create a new alert/notification rule
- import_dashboard: Create or import a Grafana dashboard
- search_logs: Search or query logs
- summarize_alerts: Summarize or list recent alerts/notifications

Output ONLY valid JSON with no extra text:
{"intent": "<intent_name>", "confidence": <0.0-1.0>}"""


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


async def classify_intent(query: str, llm: LLMProvider) -> ClassifiedIntent:
    messages = [
        {"role": "user", "content": f"{_SYSTEM_PROMPT}\n\nUser request: {query}"},
    ]

    raw = await llm.complete(messages)
    parsed = _extract_json(raw)

    intent_str = parsed.get("intent", "unknown")
    confidence = float(parsed.get("confidence", 0.5))

    try:
        intent = IntentType(intent_str)
    except ValueError:
        intent = IntentType.UNKNOWN
        confidence = 0.0

    return ClassifiedIntent(intent=intent, confidence=confidence, raw_query=query)
