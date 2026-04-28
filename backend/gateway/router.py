import asyncio
import json
import os
import uuid

import redis.asyncio as aioredis
import yaml
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(tags=["chat"])

# 읽기 전용 액션만 캐싱 (쓰기 액션은 캐시하지 않음)
_CACHEABLE_ACTIONS = {"search_logs", "summarize_alerts"}


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


def _get_cache(cfg: dict):
    from cache.semantic_cache import SemanticCache
    return SemanticCache(redis_url=cfg["services"]["redis_url"])


def _get_arq_settings(cfg: dict) -> RedisSettings:
    redis_url = cfg["services"]["redis_url"]
    # redis://redis:6379 → host=redis, port=6379
    without_scheme = redis_url.replace("redis://", "")
    host, _, port_str = without_scheme.partition(":")
    return RedisSettings(host=host, port=int(port_str or 6379))


async def _execute_action(name: str, args: dict, executors: dict) -> dict:
    if name == "create_monitoring_target":
        service_type = args.get("service_type", "local")
        service_name = args.get("service_name", "default")

        if service_type == "local":
            # 로컬: Prometheus Pull 방식 (endpoint = http://host:port/metrics)
            endpoint = args.get("endpoint", "localhost:9090")
            host, _, port = endpoint.replace("http://", "").replace("https://", "").partition(":")
            port_num = int(port.split("/")[0]) if port else 9090
            return await executors["prometheus"].add_scrape_target(
                host=host,
                port=port_num,
                job_name=service_name,
            )

        # AWS 서비스: ngrok URL 조회 → 연동 가이드 생성
        from executor.integration_guide import generate_integration_guide
        from executor.ngrok_client import get_ngrok_public_url

        try:
            ngrok_url = await get_ngrok_public_url()
        except Exception as exc:
            ngrok_url = "https://<ngrok-url-unavailable>"
            ngrok_error = str(exc)
        else:
            ngrok_error = None

        guide = generate_integration_guide(
            service_name=service_name,
            service_type=service_type,
            integration_method=args.get("integration_method", "otel-sdk"),
            ngrok_url=ngrok_url,
            environment=args.get("environment", "production"),
        )

        result: dict = {
            "status": "success",
            "service_name": service_name,
            "service_type": service_type,
            "ngrok_url": ngrok_url,
            "guide": guide,
            "message": f"AWS 서비스 연동 가이드 생성 완료: {service_name} ({service_type})",
        }
        if ngrok_error:
            result["warning"] = f"ngrok 터널 조회 실패: {ngrok_error}"
        return result
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
    if name == "list_monitoring_targets":
        return await executors["prometheus"].get_targets(
            service_filter=args.get("service_filter"),
        )
    raise HTTPException(status_code=400, detail=f"알 수 없는 액션: {name}")


# ─────────────────────────────────────────────
# POST /chat  (동기 응답)
# ─────────────────────────────────────────────

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
    cache = _get_cache(cfg)

    # ── 캐시 조회 ──
    cached = await cache.get(request.query)
    if cached:
        return {**cached, "cached": True}

    llm = _get_llm()
    executors = _get_executors(cfg)

    classified = await classify_intent(request.query, llm)
    tools = get_tools_for_intent(classified)
    # intent가 확정된 경우 해당 툴을 반드시 호출 (LLM이 텍스트로 답하는 것 방지)
    force_tool = tools[0]["name"] if tools else None

    messages = [
        {
            "role": "user",
            "content": (
                "당신은 Observability 시스템 운영 도우미입니다. "
                f"사용자 요청을 분석하여 적절한 툴을 호출하세요.\n\n요청: {request.query}"
            ),
        }
    ]

    result = await llm.function_call(messages=messages, tools=tools, force_tool=force_tool)

    if result["type"] == "function_call":
        action_name = result["name"]
        args = result["arguments"]
        action_result = await _execute_action(action_name, args, executors)

        analyzer = LLMAnalyzer(llm)
        if action_name == "search_logs":
            analysis = await analyzer.analyze_logs(action_result.get("logs", []), request.query)
        elif action_name == "summarize_alerts":
            analysis = await analyzer.summarize_alerts(action_result, request.query)
        elif action_name == "list_monitoring_targets":
            analysis = await analyzer.summarize_targets(action_result, request.query)
        else:
            analysis = action_result.get("guide") or action_result.get("message", "작업이 완료되었습니다.")

        response_body = {
            "status": "success",
            "intent": classified.intent.value,
            "action": action_name,
            "result": action_result,
            "analysis": analysis,
        }

        # ── 읽기 전용 액션만 캐시 저장 ──
        if action_name in _CACHEABLE_ACTIONS:
            await cache.set(request.query, response_body)

        return response_body

    return {
        "status": "text",
        "intent": classified.intent.value,
        "analysis": result.get("content", ""),
    }


# ─────────────────────────────────────────────
# GET /chat/stream  (SSE 스트리밍)
# ─────────────────────────────────────────────

@router.get("/chat/stream")
async def stream_chat(query: str = Query(..., description="사용자 자연어 질의")):
    """SSE 스트리밍 챗봇 응답"""
    from analyzer.llm_analyzer import LLMAnalyzer
    from intent.classifier import classify_intent
    from orchestrator.action_router import get_tools_for_intent

    cfg = _load_config()
    cache = _get_cache(cfg)
    cached = await cache.get(query)

    async def event_gen():
        try:
            # ── 캐시 히트: 저장된 결과를 SSE 이벤트로 재생 ──
            if cached:
                yield f"data: {json.dumps({'type': 'cache_hit'})}\n\n"
                if cached.get("intent"):
                    yield f"data: {json.dumps({'type': 'intent', 'intent': cached['intent']})}\n\n"
                if cached.get("action"):
                    yield f"data: {json.dumps({'type': 'action', 'name': cached['action']})}\n\n"
                if cached.get("result"):
                    yield f"data: {json.dumps({'type': 'action_result', 'result': cached['result']})}\n\n"
                if cached.get("analysis"):
                    # 분석 텍스트를 청크로 나눠 전송 (자연스러운 스트리밍 흉내)
                    text: str = cached["analysis"]
                    chunk_size = 80
                    for i in range(0, len(text), chunk_size):
                        yield f"data: {json.dumps({'type': 'text', 'content': text[i:i + chunk_size]})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # ── 캐시 미스: 정상 스트리밍 처리 ──
            llm = _get_llm()
            executors = _get_executors(cfg)

            classified = await classify_intent(query, llm)
            yield f"data: {json.dumps({'type': 'intent', 'intent': classified.intent.value})}\n\n"

            tools = get_tools_for_intent(classified)
            force_tool = tools[0]["name"] if tools else None

            messages = [
                {
                    "role": "user",
                    "content": (
                        "당신은 Observability 시스템 운영 도우미입니다. "
                        f"요청: {query}"
                    ),
                }
            ]
            result = await llm.function_call(messages=messages, tools=tools, force_tool=force_tool)

            if result["type"] == "function_call":
                action_name = result["name"]
                args = result["arguments"]
                yield f"data: {json.dumps({'type': 'action', 'name': action_name, 'args': args})}\n\n"

                action_result = await _execute_action(action_name, args, executors)
                yield f"data: {json.dumps({'type': 'action_result', 'result': action_result})}\n\n"

                analyzer = LLMAnalyzer(llm)
                # LLM 스트리밍 분석이 필요한 액션
                _LLM_STREAM_ACTIONS = {"search_logs", "summarize_alerts", "list_monitoring_targets"}

                if action_name in _LLM_STREAM_ACTIONS:
                    if action_name == "search_logs":
                        stream_input = [{"role": "user", "content": f"질문: {query}\n\n결과: {action_result}"}]
                    elif action_name == "summarize_alerts":
                        stream_input = [{"role": "user", "content": f"알림 요약 요청: {query}\n\n데이터: {action_result}"}]
                    else:  # list_monitoring_targets
                        targets = action_result.get("targets", [])
                        target_lines = "\n".join(
                            f"- {t['job']} ({t['instance']}): {t['health'].upper()}"
                            for t in targets
                        )
                        stream_input = [{
                            "role": "user",
                            "content": (
                                "당신은 시스템 모니터링 전문가입니다. "
                                "Prometheus 모니터링 대상 현황을 한국어로 요약해주세요. "
                                "DOWN 상태 서비스가 있으면 강조해주세요.\n\n"
                                f"질문: {query}\n\n"
                                f"전체 {action_result['total']}개 (UP: {action_result['up']}, DOWN: {action_result['down']}):\n"
                                f"{target_lines}"
                            ),
                        }]

                    full_analysis: list[str] = []
                    async for chunk in llm.stream(stream_input):
                        full_analysis.append(chunk)
                        yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"

                    # 읽기 전용 액션 결과 캐시 저장
                    if action_name in _CACHEABLE_ACTIONS:
                        await cache.set(query, {
                            "status": "success",
                            "intent": classified.intent.value,
                            "action": action_name,
                            "result": action_result,
                            "analysis": "".join(full_analysis),
                        })
                else:
                    # guide가 있으면 가이드 전체를, 없으면 message를 표시
                    text_content = action_result.get("guide") or action_result.get("message", "완료")
                    yield f"data: {json.dumps({'type': 'text', 'content': text_content})}\n\n"
            else:
                async for chunk in llm.stream(messages):
                    yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


# ─────────────────────────────────────────────
# POST /analyze  (ARQ Job Queue — 무거운 분석)
# ─────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    query: str
    level: str | None = None
    service: str | None = None
    time_range: str = "1h"
    group_by: str | None = None


@router.post("/analyze")
async def submit_analysis(request: AnalyzeRequest):
    """무거운 로그 분석을 ARQ Job Queue에 위임. job_id 즉시 반환."""
    cfg = _load_config()
    arq_settings = _get_arq_settings(cfg)

    job_id = str(uuid.uuid4())
    log_params = {
        "level": request.level,
        "service": request.service,
        "time_range": request.time_range,
        "group_by": request.group_by,
    }

    arq_pool = await create_pool(arq_settings)
    try:
        await arq_pool.enqueue_job("analyze_logs_job", job_id, request.query, log_params)
    finally:
        await arq_pool.aclose()

    return {"job_id": job_id, "status": "queued"}


# ─────────────────────────────────────────────
# GET /analyze/{job_id}  (결과 폴링)
# ─────────────────────────────────────────────

@router.get("/analyze/{job_id}")
async def get_analysis_result(job_id: str):
    """Redis에서 분석 결과를 조회. 완료 여부에 따라 status 반환."""
    cfg = _load_config()
    redis = await aioredis.from_url(cfg["services"]["redis_url"], decode_responses=True)
    try:
        result_raw = await redis.get(f"job:{job_id}:result")
        status = await redis.get(f"job:{job_id}:status") or "queued"
    finally:
        await redis.aclose()

    if result_raw:
        return {"job_id": job_id, "status": "completed", "result": json.loads(result_raw)}
    return {"job_id": job_id, "status": status}


# ─────────────────────────────────────────────
# GET /analyze/{job_id}/stream  (SSE: 완료 시 결과 push)
# ─────────────────────────────────────────────

@router.get("/analyze/{job_id}/stream")
async def stream_analysis_result(job_id: str):
    """SSE: Job이 완료되면 결과를 스트리밍으로 전송. 최대 2분 대기."""
    cfg = _load_config()
    redis_url = cfg["services"]["redis_url"]

    async def event_gen():
        redis = await aioredis.from_url(redis_url, decode_responses=True)
        try:
            for _ in range(60):  # 2초 × 60 = 최대 120초 대기
                result_raw = await redis.get(f"job:{job_id}:result")
                if result_raw:
                    yield f"data: {json.dumps({'type': 'completed', 'result': json.loads(result_raw)})}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                yield f"data: {json.dumps({'type': 'status', 'status': 'processing'})}\n\n"
                await asyncio.sleep(2)
            yield f"data: {json.dumps({'type': 'error', 'message': '분석 시간 초과 (120초)'})}\n\n"
            yield "data: [DONE]\n\n"
        finally:
            await redis.aclose()

    return StreamingResponse(event_gen(), media_type="text/event-stream")
