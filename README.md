# Auto Logging & Monitoring by LLM

> 자연어 챗봇으로 Observability 시스템을 자동 구축·설정·조회하는 AI 기반 모니터링 자동화 서비스

단국대학교 포트폴리오 프로젝트 | 한국 취업 시장 타깃

---

## 목차

- [프로젝트 개요](#프로젝트-개요)
- [시스템 아키텍처](#시스템-아키텍처)
- [기술 스택](#기술-스택)
- [주요 기능](#주요-기능)
- [디렉토리 구조](#디렉토리-구조)
- [시작하기](#시작하기)
- [이용 방법](#이용-방법)
- [API 명세](#api-명세)

---

## 프로젝트 개요

기존 Observability 시스템(Prometheus, Grafana, Elasticsearch 등)은 전문 지식 없이 설정하기 어렵습니다.  
이 프로젝트는 **자연어 챗봇 인터페이스** 하나로 모니터링 대상 추가, 알림 규칙 생성, 로그 검색, 대시보드 생성을 수행합니다.

### 핵심 설계 원칙

```
자연어 → Intent 분류 → 허용된 Action 검증 → 실행
```

임의 Shell 실행, 위험한 인프라 작업을 원천 차단하고 **허용된 5+1개 액션**만 실행합니다.

---

## 시스템 아키텍처

```
┌─────────────────────────────────────────────┐
│           React 챗봇 UI                      │
│     (SSE 스트리밍 + Grafana iframe 임베드)    │
└───────────────────┬─────────────────────────┘
                    │ SSE / REST
┌───────────────────▼─────────────────────────┐
│             FastAPI Backend                  │
│                                              │
│  Intent Classifier → Orchestrator → Executor │
│  (LLM Function Calling 기반 안전한 실행)      │
│                                              │
│  ┌─────────┐  ┌──────────┐  ┌────────────┐  │
│  │ LLM     │  │ Semantic │  │ ARQ Job    │  │
│  │Provider │  │ Cache    │  │ Queue      │  │
│  │Abstrac. │  │ (Redis)  │  │ (무거운    │  │
│  └─────────┘  └──────────┘  │  분석용)   │  │
│                              └────────────┘  │
└──────────────┬──────────────────────────────┘
               │
┌──────────────▼──────────────────────────────┐
│          Observability Stack                 │
│                                              │
│  Prometheus  Grafana  Elasticsearch  Kibana  │
│  Alertmanager  Tempo  OTel Collector         │
│  Fluent Bit  Langfuse  Redis  ngrok          │
└─────────────────────────────────────────────┘
               ↑  OTel Push (ngrok 터널)
┌──────────────┴──────────────────────────────┐
│          AWS 외부 서비스 (선택)               │
│     EC2 / ECS / Lambda + OTel SDK           │
└─────────────────────────────────────────────┘
```

### 데이터 흐름

1. 사용자가 챗봇에 자연어로 요청 입력
2. LLM이 **Intent 분류** (6종)
3. Orchestrator가 **허용된 Action 검증**
4. LLM **Function Calling**으로 파라미터 추출 (툴 강제 호출)
5. Executor가 해당 Observability API 호출
6. LLM이 결과를 자연어로 **SSE 스트리밍** 응답

---

## 기술 스택

### Observability Core

| 도구 | 역할 |
|------|------|
| Prometheus | 메트릭 수집 및 저장 |
| Grafana | 대시보드 시각화 (iframe embed) |
| Elasticsearch | 로그 저장 및 풀텍스트 검색 |
| Kibana | 로그 시각화 UI |
| OpenTelemetry Collector | traces / metrics / logs 통합 수집 |
| Tempo | 분산 트레이싱 백엔드 |
| Alertmanager | 알림 라우팅 및 중복 제거 |
| Fluent Bit | 로그 수집 및 전처리 |
| Langfuse | LLM 호출 트레이싱 · 비용 · 품질 평가 (자체 호스팅) |
| ngrok | 외부 서비스 → OTel Collector Push용 터널 |

### Backend

| 기술 | 역할 |
|------|------|
| FastAPI (Python) | REST API + SSE 스트리밍 |
| ARQ + Redis | 무거운 LLM 분석 비동기 Job Queue |
| Semantic Cache | 동일 쿼리 재요청 시 LLM 비용 절감 |

### Frontend

| 기술 | 역할 |
|------|------|
| React 18 + TypeScript | 챗봇 UI |
| Vite | 개발 서버 및 번들러 |
| react-markdown | LLM 응답 마크다운 렌더링 |
| Grafana iframe | 대시보드 실시간 embed |

### LLM

| 환경 | Provider | 모델 |
|------|----------|------|
| 개발 / MVP | OpenAI | gpt-4o-mini |
| 발표 / 데모 | Anthropic | claude-sonnet-4-20250514 |
| 오프라인 데모 | Ollama | llama3 |

`config.yml` 한 줄로 Provider 교체 가능한 **Provider Agnostic** 구조

---

## 주요 기능

### 허용된 Action 목록

| Action | 설명 | 연동 시스템 |
|--------|------|-------------|
| `create_monitoring_target` | 로컬 / AWS 외부 서비스 모니터링 추가 + OTel 연동 가이드 자동 생성 | Prometheus, ngrok |
| `create_alert_rule` | 알림 규칙 생성 (metric, threshold, severity) | Prometheus, Alertmanager |
| `import_dashboard` | Grafana 대시보드 자동 생성 | Grafana |
| `search_logs` | Elasticsearch 로그 검색 + LLM 분석 | Elasticsearch |
| `summarize_alerts` | 최근 알림 현황 요약 | Alertmanager |
| `list_monitoring_targets` | 현재 모니터링 중인 서비스 UP/DOWN 현황 | Prometheus |

### AWS 외부 서비스 연동

AWS EC2 / ECS / Lambda에 배포된 서비스는 Pull 방식이 불가능합니다.  
**ngrok 터널 → OTel Collector Push** 방식으로 자동 연동 가이드를 생성합니다.

지원 연동 방식:
- **OTel SDK** — Spring Boot / Node.js / Python 코드 삽입 가이드 자동 생성
- **AWS Lambda Layer** — OTel Lambda Layer + collector.yml 구성 가이드
- **Fluent Bit** — 사이드카 컨테이너 로그 수집 구성
- **Prometheus Exporter** — Actuator/Micrometer 기반 Pull 방식

### Langfuse LLM 트레이싱

모든 LLM 호출에 자동으로 트레이스 삽입:
- Token 사용량 및 비용 추적
- 응답 레이턴시 모니터링
- Function Calling 툴 선택 기록
- 에러 발생 시 ERROR 레벨 기록

---

## 디렉토리 구조

```
.
├── docker-compose.yml           # Observability 전체 스택
├── docker-compose.dev.yml       # 개발 환경 오버라이드 (Backend 로컬 실행)
├── .env.example                 # 환경변수 템플릿
├── config/
│   ├── prometheus/prometheus.yml
│   ├── alertmanager/alertmanager.yml
│   ├── grafana/provisioning/
│   ├── elasticsearch/
│   ├── otel-collector/otel-collector.yml
│   ├── tempo/tempo.yml
│   └── fluent-bit/fluent-bit.conf
├── backend/
│   ├── main.py                  # FastAPI 진입점
│   ├── config.yml               # LLM Provider + 서비스 URL 설정
│   ├── requirements.txt
│   ├── llm/
│   │   ├── interface.py         # Provider 추상화 (ABC)
│   │   ├── openai_provider.py   # GPT-4o mini
│   │   ├── claude_provider.py   # Claude Sonnet 4
│   │   ├── ollama_provider.py   # 오프라인 Ollama
│   │   └── tracing.py           # Langfuse 싱글톤 클라이언트
│   ├── intent/
│   │   └── classifier.py        # 자연어 → Intent 6종 분류
│   ├── orchestrator/
│   │   └── action_router.py     # 허용 Action 검증 + 툴 정의
│   ├── executor/
│   │   ├── prometheus.py        # Prometheus API
│   │   ├── grafana.py           # Grafana API
│   │   ├── elasticsearch.py     # Elasticsearch API
│   │   ├── alertmanager.py      # Alertmanager API
│   │   ├── ngrok_client.py      # ngrok 터널 URL 동적 조회
│   │   └── integration_guide.py # 외부 서비스 연동 가이드 생성
│   ├── analyzer/
│   │   └── llm_analyzer.py      # LLM 기반 로그/알림/타겟 분석
│   ├── gateway/
│   │   └── router.py            # API 라우터 (chat, analyze 엔드포인트)
│   ├── jobs/
│   │   └── analysis_worker.py   # ARQ 비동기 Job Worker
│   └── cache/
│       └── semantic_cache.py    # Redis 기반 Semantic Cache
└── frontend/
    ├── package.json
    └── src/
        ├── App.tsx
        └── components/
            ├── ChatBot/         # SSE 스트리밍 챗봇 UI
            └── GrafanaEmbed/    # Grafana iframe 컴포넌트
```

---

## 시작하기

### 사전 요구사항

- Docker Desktop (Windows / Mac)
- Node.js 18+
- Python 3.11+
- ngrok 계정 (외부 서비스 연동 시)

### 1. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일 편집:

```dotenv
# 필수
OPENAI_API_KEY=sk-...

# Langfuse (http://localhost:3002 에서 프로젝트 생성 후 입력)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3002

# ngrok (외부 서비스 연동 시 - https://dashboard.ngrok.com/authtokens)
NGROK_AUTHTOKEN=your-token
NGROK_API_URL=http://localhost:4040
```

### 2. Observability 스택 기동

```bash
# 개발 모드 (Backend는 로컬에서 별도 실행)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

서비스 접속 URL:

| 서비스 | URL |
|--------|-----|
| Grafana | http://localhost:3001 (admin / admin123) |
| Kibana | http://localhost:5601 |
| Prometheus | http://localhost:9090 |
| Alertmanager | http://localhost:9093 |
| Langfuse | http://localhost:3002 |
| ngrok 대시보드 | http://localhost:4040 |

### 3. Backend 실행

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

ARQ Worker (무거운 분석 비동기 처리):
```bash
# 별도 터미널에서
cd backend
arq jobs.analysis_worker.WorkerSettings
```

### 4. Frontend 실행

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 `http://localhost:5173` 접속

---

## 이용 방법

### 챗봇 입력 예시

**모니터링 대상 추가 (AWS EC2)**
```
AWS에 배포된 order-service 모니터링 추가해줘
```
→ service_type 자동 판단 → ngrok URL 조회 → OTel SDK 연동 가이드 (Spring Boot / Node.js / Python) 자동 생성

**로그 검색 및 분석**
```
order-service 에러 로그 요약해줘
최근 1시간 ERROR 레벨 로그 분석해줘
```
→ Elasticsearch 검색 → LLM이 패턴·이상 징후 자연어 요약

**알림 현황 확인**
```
현재 알림 현황 알려줘
critical 알림 있어?
```
→ Alertmanager 조회 → LLM이 심각도별 요약

**모니터링 대상 목록 조회**
```
현재 연동된 서비스 목록 알려줘
모니터링 중인 서비스 현황 보여줘
```
→ Prometheus Targets 조회 → UP/DOWN 상태 포함 요약

**알림 규칙 생성**
```
CPU 사용률 90% 초과 시 critical 알림 만들어줘
```
→ Prometheus alert rule 생성

**Grafana 대시보드 생성**
```
order-service 대시보드 만들어줘
```
→ Grafana 대시보드 자동 생성 → UI에 iframe으로 즉시 표시

### LLM Provider 전환

`backend/config.yml` 수정:

```yaml
llm:
  provider: "openai"        # 개발용
  model: "gpt-4o-mini"

  # provider: "claude"      # 발표용
  # model: "claude-sonnet-4-20250514"

  # provider: "ollama"      # 오프라인 데모용
  # model: "llama3"
```

### AWS 외부 서비스 OTel 연동 흐름

```
AWS 서비스  →  OTel SDK  →  ngrok 터널  →  OTel Collector  →  Prometheus / Tempo / Elasticsearch
```

1. 챗봇: `"AWS에 배포된 [서비스명] 모니터링 추가해줘"`
2. 응답으로 받은 연동 가이드를 AWS 서비스에 적용
3. 메트릭은 Grafana, 트레이스는 Tempo, 로그는 Kibana에서 확인

---

## API 명세

### POST `/api/v1/chat`
동기 방식 챗봇 응답

```json
// Request
{ "query": "에러 로그 보여줘", "session_id": "optional" }

// Response
{
  "status": "success",
  "intent": "search_logs",
  "action": "search_logs",
  "result": { ... },
  "analysis": "최근 1시간 ERROR 로그 분석 결과..."
}
```

### GET `/api/v1/chat/stream?query=...`
SSE 스트리밍 챗봇 응답

```
data: {"type": "intent", "intent": "search_logs"}
data: {"type": "action", "name": "search_logs", "args": {...}}
data: {"type": "action_result", "result": {...}}
data: {"type": "text", "content": "분석 결과 텍스트 청크..."}
data: [DONE]
```

### POST `/api/v1/analyze`
무거운 분석 작업 비동기 처리 (ARQ Job Queue)

```json
// Request
{ "query": "에러 패턴 분석", "service": "order-service", "time_range": "1h" }

// Response (즉시)
{ "job_id": "uuid", "status": "queued" }
```

### GET `/api/v1/analyze/{job_id}`
분석 결과 폴링

```json
{ "job_id": "uuid", "status": "completed", "result": "..." }
```

### GET `/api/v1/analyze/{job_id}/stream`
SSE: 분석 완료 시 결과 push (최대 120초 대기)

---

## 보안 설계

- **허용 목록 기반 실행**: 6개 Action 이외 실행 불가
- **임의 Shell 실행 금지**: LLM이 직접 시스템 명령 수행 불가
- **AWS 서비스 직접 수정 금지**: 연동 가이드 제공만 허용
- **Langfuse 감사 로그**: 모든 LLM 호출 비용·레이턴시·툴 선택 기록

---

## 개발 환경 정보

- Python 3.11+
- Node.js 18+
- Docker Desktop
- 로컬 머신 개발 → Oracle Cloud Free Tier 배포 예정
