import json
import os

import yaml
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(tags=["chat"])


def _load_config() -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "config.yml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_llm():
    from llm import get_provider
    return get_provider()


def _get_executors(cfg: dict) -> dict:
    svc = cfg["services"]
    from executor.alertmanager import AlertmanagerExecutor
    from executor.elasticsearch import ElasticsearchExecutor
    from executor.grafana import GrafanaExecutor
    from executor.prometheus import PrometheusExecutor

    return {
        "prometheus": PrometheusExecutor(svc["prometheus_url"]),
        "grafana": GrafanaExecutor(
            svc["grafana_url"],
            svc["grafana_user"],
            svc["grafana_password"],
        ),
        "elasticsearch": ElasticsearchExecutor(svc["elasticsearch_url"]),
        "alertmanager": AlertmanagerExecutor(svc["alertmanager_url"]),
    }


async def _execute_action(name: str, args: dict, executors: dict) -> dict:
    if name == "create_monitoring_target":
        return await executors["prometheus"].add_scrape_target(
            host=args.get("host", ""),
            port=int(args.get("port", 9090)),
            job_name=args.get("job_name", "default"),
        )
    if name == "create_alert_rule":
        return await executors["prometheus"].create_alert_rule(
            metric=args.get("metric", ""),
            threshold=float(args.get("threshold", 0)),
            duration=args.get("duration", "5m"),
            severity=args.get("severity", "warning"),
        )
    if name == "import_dashboard":
        return await executors["grafana"].import_dashboard(
            dashboard_type=args.get("dashboard_type", "service"),
            service_name=args.get("service_name", "default"),
        )
    if name == "search_logs":
        return await executors["elasticsearch"].search_logs(
            level=args.get("level"),
            service=args.get("service"),
            time_range=args.get("time_range", "1h"),
            group_by=args.get("group_by"),
        )
    if name == "summarize_alerts":
        return await executors["alertmanager"].get_alerts(
            time_range=args.get("time_range", "1h"),
            service=args.get("service"),
        )
    raise HTTPException(status_code=400, detail=f"알 수 없는 액션: {name}")


class ChatRequest(BaseModel):
    query: str
    session_id: str | None = None


@router.post("/chat")
async def chat(request: ChatRequest):
    """자연어 → Intent 분류 → Function Calling → 실행 (동기)"""
    from analyzer.llm_analyzer import LLMAnalyzer
    from intent.classifier import classify_intent
    from orchestrator.action_router import get_tools_for_intent

    cfg = _load_config()
    llm = _get_llm()
    executors = _get_executors(cfg)

    classified = await classify_intent(request.query, llm)
    tools = get_tools_for_intent(classified)

    messages = [
        {
            "role": "user",
            "content": (
                "당신은 Observability 시스템 운영 도우미입니다. "
                f"사용자 요청을 분석하여 적절한 툴을 호출하세요.\n\n요청: {request.query}"
            ),
        }
    ]

    result = await llm.function_call(messages=messages, tools=tools)

    if result["type"] == "function_call":
        action_name = result["name"]
        args = result["arguments"]
        action_result = await _execute_action(action_name, args, executors)

        analyzer = LLMAnalyzer(llm)
        if action_name == "search_logs":
            analysis = await analyzer.analyze_logs(action_result.get("logs", []), request.query)
        elif action_name == "summarize_alerts":
            analysis = await analyzer.summarize_alerts(action_result, request.query)
        else:
            analysis = action_result.get("message", "작업이 완료되었습니다.")

        return {
            "status": "success",
            "intent": classified.intent.value,
            "action": action_name,
            "result": action_result,
            "analysis": analysis,
        }

    return {
        "status": "text",
        "intent": classified.intent.value,
        "analysis": result.get("content", ""),
    }


@router.get("/chat/stream")
async def stream_chat(query: str = Query(..., description="사용자 자연어 질의")):
    """SSE 스트리밍 챗봇 응답"""
    from analyzer.llm_analyzer import LLMAnalyzer
    from intent.classifier import classify_intent
    from orchestrator.action_router import get_tools_for_intent

    async def event_gen():
        try:
            cfg = _load_config()
            llm = _get_llm()
            executors = _get_executors(cfg)

            classified = await classify_intent(query, llm)
            yield f"data: {json.dumps({'type': 'intent', 'intent': classified.intent.value})}\n\n"

            tools = get_tools_for_intent(classified)

            messages = [
                {
                    "role": "user",
                    "content": (
                        "당신은 Observability 시스템 운영 도우미입니다. "
                        f"요청: {query}"
                    ),
                }
            ]
            result = await llm.function_call(messages=messages, tools=tools)

            if result["type"] == "function_call":
                action_name = result["name"]
                args = result["arguments"]
                yield f"data: {json.dumps({'type': 'action', 'name': action_name, 'args': args})}\n\n"

                action_result = await _execute_action(action_name, args, executors)
                yield f"data: {json.dumps({'type': 'action_result', 'result': action_result})}\n\n"

                analyzer = LLMAnalyzer(llm)
                if action_name == "search_logs":
                    stream = analyzer.llm.stream(
                        [{"role": "user", "content": f"질문: {query}\n\n결과: {action_result}"}]
                    )
                elif action_name == "summarize_alerts":
                    stream = analyzer.llm.stream(
                        [{"role": "user", "content": f"알림 요약 요청: {query}\n\n데이터: {action_result}"}]
                    )
                else:
                    yield f"data: {json.dumps({'type': 'text', 'content': action_result.get('message', '완료')})}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                async for chunk in stream:
                    yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"
            else:
                async for chunk in llm.stream(messages):
                    yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
