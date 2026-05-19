# Auto Logging & Monitoring by LLM

> 자연어 챗봇으로 Observability 시스템을 자동 구축·설정·조회하는 AI 기반 모니터링 자동화 서비스

---

## 목차

- [프로젝트 개요](#프로젝트-개요)
- [시스템 아키텍처](#시스템-아키텍처)
- [기술 스택](#기술-스택)
- [주요 기능](#주요-기능)
- [실제 서비스 연동 데모](#실제-서비스-연동-데모)
- [디렉토리 구조](#디렉토리-구조)
- [시작하기](#시작하기)
- [EC2 Host Metrics 설정](#ec2-host-metrics-설정)
- [이용 방법](#이용-방법)
- [API 명세](#api-명세)
- [트러블슈팅](#트러블슈팅)

---

## 프로젝트 개요

기존 Observability 시스템(Prometheus, Grafana, Elasticsearch 등)은 전문 지식 없이 설정하기 어렵습니다.  
이 프로젝트는 **자연어 챗봇 인터페이스** 하나로 모니터링 대상 추가, 알림 규칙 생성, 로그 검색, 대시보드 생성·편집을 수행합니다.

### 핵심 설계 원칙

```
자연어 → Intent 분류 → 허용된 Action 검증 → 실행
```

임의 Shell 실행, 위험한 인프라 작업을 원천 차단하고 **허용된 7개 액션**만 실행합니다.

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
│          Observability Stack (로컬 Docker)   │
│                                              │
│  Prometheus  Grafana  Elasticsearch  Kibana  │
│  Alertmanager  Tempo  OTel Collector         │
│  Fluent Bit  Langfuse  Redis  ngrok          │
└─────────────────────────────────────────────┘
               ↑  OTel Push (OTLP/HTTP via ngrok)
┌──────────────┴──────────────────────────────┐
│          AWS EC2 실제 운영 서비스             │
│                                              │
│  Spring Boot (magambell-blue/green)          │
│  + OTel Java Agent v2.27.0                  │
│  + OTel Collector (Host Metrics)             │
└─────────────────────────────────────────────┘
```

### OTel Push 데이터 흐름

```
EC2 Spring Boot
  └─ OTel Java Agent
        └─ OTLP/HTTP (포트 4318)
              └─ ngrok 공개 URL
                    └─ 로컬 OTel Collector
                          ├─ Prometheus (메트릭)
                          ├─ Tempo (트레이스)
                          └─ Elasticsearch (로그)

EC2 Host
  └─ OTel Collector (hostmetrics receiver)
        └─ OTLP/HTTP → ngrok → 로컬 OTel Collector → Prometheus
```

> **주의**: ngrok 무료 플랜은 gRPC(포트 4317)를 지원하지 않습니다.  
> 반드시 HTTP/Protobuf(포트 4318)를 사용해야 합니다.
> ```bash
> export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
> export OTEL_EXPORTER_OTLP_ENDPOINT=https://<ngrok-url>
> ```

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
| `import_dashboard` | Grafana 대시보드 자동 생성 (서비스용 / EC2 호스트용) | Grafana |
| `modify_dashboard` | 기존 대시보드에 패널 추가·삭제. PromQL 자동 검증·보정 | Grafana, Prometheus |
| `search_logs` | Elasticsearch 로그 검색 (한국어 레벨·서비스·시간 범위 정규화) | Elasticsearch |
| `summarize_alerts` | 최근 알림 현황 요약 (Alertmanager 없을 시 Prometheus ALERTS 쿼리 fallback) | Alertmanager, Prometheus |
| `list_monitoring_targets` | 현재 모니터링 중인 서비스 UP/DOWN 현황 | Prometheus |

### 대시보드 자동 생성 (import_dashboard)

두 가지 타입을 자동 판별합니다.

**서비스 대시보드** (`dashboard_type: service`) — OTel Java Agent 메트릭 기반
- Request Rate (rps) — `otel_http_server_request_duration_seconds_count`
- Error Rate (4xx+5xx) — `http_response_status_code` 레이블 필터
- Latency p99 (ms) — `histogram_quantile(0.99, ...)`
- JVM CPU Utilization, JVM Heap Memory, JVM Thread Count
- DB Connection Pool (HikariCP)

**EC2 Host 대시보드** (`dashboard_type: node`) — OTel hostmetrics receiver 기반
- CPU Utilization (user/system)
- Memory Utilization
- Disk I/O (bytes/s), Disk IOPS
- Network I/O (rx/tx)
- System Load Average
- Filesystem Utilization

### 대시보드 편집 (modify_dashboard)

기존 대시보드에 자연어로 패널을 추가하거나 삭제합니다.  
패널 추가 시 LLM이 생성한 PromQL을 Prometheus에 실제 쿼리해서 검증하고, 데이터가 없으면 유사 메트릭을 자동 탐색·보정합니다.

```
사용자: "magambell-dev 대시보드에 JVM GC 메트릭 추가해줘"
→ LLM: metric_expr = rate(otel_jvm_gc_duration_seconds_count{exported_job="magambell-dev"}[5m])
→ Prometheus 검증 → 데이터 확인 → 패널 추가
```

### 로그 검색 정규화

LLM이 다양한 표현으로 파라미터를 생성하더라도 올바르게 처리합니다.

| LLM 출력 | 정규화 결과 |
|---------|------------|
| `level="경고 수준"` | `SeverityText.keyword: WARN` |
| `level="warning"` | `SeverityText.keyword: WARN` |
| `service="all"` | 서비스 필터 제거 (전체 조회) |
| `time_range="last_24_hours"` | `timedelta(hours=24)` |
| `time_range="오늘"` | `timedelta(hours=24)` |

OTel Collector가 수집하는 실제 ES 필드명:
- 레벨: `SeverityText.keyword` (INFO / WARN / ERROR)
- 서비스: `Resource.service.name.keyword`
- 타임스탬프: `@timestamp`

---

## 실제 서비스 연동 데모

실제 운영 중인 Spring Boot 서비스(magambell-dev)를 연동한 결과입니다.

### 서비스 대시보드 — magambell-dev

[LLM_ServiceDashboard.pdf](https://github.com/user-attachments/files/27982905/LLM_ServiceDashboard.pdf)

- **Request Rate**: `/api/v1/order`, `/api/v1/store` 등 실제 API 엔드포인트별 요청 수
- **Error Rate**: 4xx/5xx 응답 실시간 추적
- **Latency p99**: 실제 트래픽 기준 99분위 지연시간
- **JVM Heap**: 세 개 힙 영역(Eden, Survivor, Old) 실시간 메모리
- **DB Connection Pool**: HikariCP idle/used 커넥션 현황

### EC2 Host 대시보드

<img width="1920" height="1098" alt="image" src="https://github.com/user-attachments/assets/4d7af6e9-52cf-409d-bd94-cf3720d5a8ea" />

- OTel Collector hostmetrics receiver로 수집
- EC2 기본 디스크: `xvda` / `xvda1`
- 실시간 CPU, 메모리, 디스크 I/O, 네트워크 I/O, 파일시스템 사용률

### 자연어 대시보드 편집

<img width="1919" height="906" alt="스크린샷 2026-05-19 120509" src="https://github.com/user-attachments/assets/5c44caa4-7144-43a1-b633-aba9af99f2fd" />

"magambell-dev (node) 대시보드에 디스크 IOPS 패널 추가해줘"  
→ Prometheus 메트릭 자동 탐색 → `otel_system_disk_operations_total` 보정 → 패널 추가

### 알림 규칙 생성

<img width="1919" height="903" alt="스크린샷 2026-05-19 114829" src="https://github.com/user-attachments/assets/742c2622-3aee-4a1d-b1b8-b59f899713de" />

"magambell-dev 서비스 CPU 사용률 80% 넘으면 warning 알림 만들어줘"  
→ Prometheus alert rule 자동 생성 완료

---

## 디렉토리 구조

```
.
├── docker-compose.yml                    # Observability 전체 스택
├── .env.example                          # 환경변수 템플릿
├── config/
│   ├── prometheus/prometheus.yml
│   ├── alertmanager/alertmanager.yml
│   ├── grafana/provisioning/
│   ├── otel-collector/
│   │   ├── otel-collector.yml            # 로컬 OTel Collector (수신)
│   │   └── otel-collector-ec2-hostmetrics.yml  # EC2 호스트 메트릭 수집용
│   ├── tempo/tempo.yml
│   └── fluent-bit/fluent-bit.conf
├── scripts/
│   ├── setup-ec2-hostmetrics.sh          # EC2 OTel Collector 자동 설치 스크립트
│   └── tunnel-prod.ps1                   # EC2 SSH 접속 헬퍼
├── backend/
│   ├── main.py
│   ├── config.yml                        # LLM Provider + 서비스 URL (로컬)
│   ├── config.prod.yml                   # 프로덕션 환경 설정
│   ├── intent/
│   │   └── classifier.py                 # 자연어 → Intent 7종 분류
│   ├── orchestrator/
│   │   └── action_router.py              # 허용 Action 검증 + 툴 정의 (PromQL 예시 포함)
│   ├── executor/
│   │   ├── prometheus.py                 # Prometheus API (read_only 지원)
│   │   ├── grafana.py                    # Grafana API + Prometheus 메트릭 검증
│   │   ├── elasticsearch.py              # ES API (레벨·서비스·시간 정규화)
│   │   ├── alertmanager.py               # Alertmanager (Prometheus fallback)
│   │   ├── ngrok_client.py
│   │   └── integration_guide.py
│   ├── cache/
│   │   └── semantic_cache.py             # Redis 기반 해시 캐시 (쓰기 액션 제외)
│   └── gateway/
│       └── router.py                     # API 라우터 + _resolve() Docker 환경변수 처리
└── frontend/
    └── src/
        ├── App.tsx
        └── components/
            ├── ChatBot/
            └── GrafanaEmbed/
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

# ngrok (외부 서비스 연동 필수 - https://dashboard.ngrok.com/authtokens)
NGROK_AUTHTOKEN=your-token

# Langfuse (http://localhost:3002 에서 프로젝트 생성 후 입력, 선택)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

### 2. Observability 스택 기동

```bash
docker compose up -d
```

서비스 접속 URL:

| 서비스 | URL | 계정 |
|--------|-----|------|
| 챗봇 UI | http://localhost:5173 | - |
| Grafana | http://localhost:3001 | admin / admin123 |
| Kibana | http://localhost:5601 | - |
| Prometheus | http://localhost:9090 | - |
| Alertmanager | http://localhost:9093 | - |
| Langfuse | http://localhost:3002 | - |
| ngrok 대시보드 | http://localhost:4040 | - |

### 3. Frontend 실행

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 `http://localhost:5173` 접속

---

## EC2 Host Metrics 설정

EC2 서버의 CPU·메모리·디스크·네트워크 메트릭을 로컬 Prometheus로 수집합니다.

### 구조

```
EC2 OTel Collector (hostmetrics receiver)
  → OTLP/HTTP → ngrok → 로컬 OTel Collector → Prometheus
```

### EC2에서 설치

ngrok URL 확인 후 (로컬: `curl http://localhost:4040/api/tunnels`):

```bash
# EC2 SSH 접속 후 실행
NGROK_URL=https://<your-ngrok-url>

sudo mkdir -p /opt/otel-hostmetrics

# 설정 파일 생성
sudo tee /opt/otel-hostmetrics/config.yml > /dev/null << YAML
receivers:
  hostmetrics:
    collection_interval: 30s
    scrapers:
      cpu:
        metrics:
          system.cpu.utilization:
            enabled: true
      memory:
        metrics:
          system.memory.utilization:
            enabled: true
      disk: {}
      filesystem:
        metrics:
          system.filesystem.utilization:
            enabled: true
      network: {}
      load: {}

processors:
  batch:
    timeout: 10s
  resource:
    attributes:
      - key: service.name
        value: "ec2-host"
        action: upsert

exporters:
  otlphttp:
    endpoint: "${NGROK_URL}"
    tls:
      insecure: false

service:
  pipelines:
    metrics:
      receivers: [hostmetrics]
      processors: [resource, batch]
      exporters: [otlphttp]
YAML

sudo sed -i "s|\${NGROK_URL}|${NGROK_URL}|g" /opt/otel-hostmetrics/config.yml

# 바이너리 다운로드
curl -sL "https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v0.99.0/otelcol-contrib_0.99.0_linux_amd64.tar.gz" -o /tmp/otelcol.tar.gz
sudo tar -xzf /tmp/otelcol.tar.gz -C /opt/otel-hostmetrics otelcol-contrib
sudo chmod +x /opt/otel-hostmetrics/otelcol-contrib

# 백그라운드 실행
nohup sudo /opt/otel-hostmetrics/otelcol-contrib \
  --config=/opt/otel-hostmetrics/config.yml \
  > /tmp/otelcol-hostmetrics.log 2>&1 &
```

### 수집 확인 (30초 후)

```bash
# 로컬에서
curl -s "http://localhost:9090/api/v1/query?query=otel_system_cpu_utilization_ratio" \
  | grep -o '"exported_job":"[^"]*"' | head -1
# → "exported_job":"ec2-host"
```

---

## 이용 방법

### 챗봇 입력 예시

**서비스 대시보드 생성**
```
magambell-dev 서비스 대시보드 만들어줘
```
→ Request Rate / Error Rate / Latency p99 / JVM / DB Connection Pool 패널 자동 생성

**EC2 호스트 대시보드 생성**
```
node exporter 대시보드 생성해줘
ec2 시스템 대시보드 만들어줘
```
→ CPU / Memory / Disk / Network / Load / Filesystem 패널 자동 생성

**대시보드 패널 추가**
```
magambell-dev 대시보드에 JVM GC 메트릭 추가해줘
ec2-host 대시보드에 디스크 IOPS 패널 추가해줘
magambell-dev 대시보드에 DB 커넥션 풀 패널 추가해줘
```
→ PromQL 자동 생성 → Prometheus 검증 → 패널 추가 (데이터 없을 시 자동 보정)

**대시보드 패널 삭제**
```
magambell-dev 대시보드에서 JVM Thread Count 패널 삭제해줘
```

**로그 검색**
```
magambell-dev 서비스 로그 보여줘
경고 수준 로그 검색해줘
지난 24시간 INFO 로그 보여줘
```

**알림 규칙 생성**
```
magambell-dev 서비스 CPU 사용률 80% 넘으면 warning 알림 만들어줘
메모리 사용량 90% 초과하면 critical 알림 설정해줘
```

**모니터링 현황 조회**
```
현재 연동된 서비스 목록 알려줘
알림 현황 보여줘
```

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
  "result": { "total": 42, "logs": [...] },
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

### GET `/api/v1/health/services`
연결된 서비스 헬스체크

```json
{
  "prometheus": "ok",
  "grafana": "ok",
  "elasticsearch": "ok",
  "alertmanager": "ok",
  "ngrok_tunnel": "https://xxxx.ngrok-free.app"
}
```

---

## 트러블슈팅

### 로그 검색이 항상 0건 반환

**원인 1: Elasticsearch 필드명 불일치**

OTel Collector가 수집한 로그는 표준 필드명과 다릅니다.

| 일반적인 필드 | OTel 실제 필드 |
|-------------|---------------|
| `level` | `SeverityText.keyword` |
| `service` | `Resource.service.name.keyword` |

인덱스 패턴도 `logs*`가 아닌 `*logs*`를 사용해야 `otel-logs` 인덱스가 포함됩니다.

**원인 2: Redis 캐시에 오래된 결과 저장**

```bash
docker exec redis redis-cli FLUSHALL
```

**원인 3: LLM이 비표준 파라미터 생성**

| LLM 출력 | 처리 방법 |
|---------|---------|
| `service="all"` | `_SERVICE_SKIP` 집합으로 필터 무시 |
| `level="경고 수준"` | `_LEVEL_ALIAS` substring 매핑 → WARN |
| `time_range="last_24_hours"` | `_TIME_RANGE_ALIAS` 정규화 → 24h |

---

### 대시보드 패널에 데이터 없음 (No data)

**원인: PromQL이 실제 메트릭명과 불일치**

이 스택의 OTel 메트릭은 `otel_` 접두사와 `exported_job` 레이블을 사용합니다.  
일반적인 node_exporter / Micrometer 메트릭명과 다릅니다.

| 잘못된 예 | 올바른 예 |
|---------|---------|
| `http_requests_total` | `otel_http_server_request_duration_seconds_count{exported_job="magambell-dev"}` |
| `node_cpu_seconds_total` | `otel_system_cpu_utilization_ratio{exported_job="ec2-host"}` |
| `jvm_memory_used_bytes` | `otel_jvm_memory_used_bytes{exported_job="magambell-dev"}` |

실제 사용 가능한 메트릭 조회:

```bash
curl -s "http://localhost:9090/api/v1/label/__name__/values" \
  | tr ',' '\n' | grep "otel_"
```

---

### ngrok 연결 실패 (ERR_NGROK_107)

`.env`의 `NGROK_AUTHTOKEN`이 만료됐거나 유효하지 않습니다.  
[ngrok 대시보드](https://dashboard.ngrok.com/authtokens)에서 새 토큰 발급 후:

```bash
# .env 업데이트 후
docker compose up -d --force-recreate ngrok
```

---

### ngrok gRPC 연결 불가 (Spring Boot OTel)

ngrok 무료 플랜은 gRPC(포트 4317)를 지원하지 않습니다.  
Spring Boot OTel Java Agent 실행 시 반드시 HTTP/Protobuf로 변경:

```bash
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_EXPORTER_OTLP_ENDPOINT=https://<ngrok-url>  # 4318 OTLP HTTP
export OTEL_SERVICE_NAME=your-service-name
```

---

### Docker 컨테이너 내 Redis/Prometheus 연결 실패

Backend가 Docker 컨테이너로 실행 중일 때 `localhost`로는 다른 컨테이너에 접근할 수 없습니다.  
`docker-compose.yml`의 환경변수가 config.yml보다 우선 적용됩니다:

```yaml
# docker-compose.yml backend 서비스
environment:
  - REDIS_URL=redis://redis:6379        # 컨테이너 서비스명 사용
  - PROMETHEUS_URL=http://prometheus:9090
  - ELASTICSEARCH_URL=http://elasticsearch:9200
```

---

## 보안 설계

- **허용 목록 기반 실행**: 7개 Action 이외 실행 불가
- **임의 Shell 실행 금지**: LLM이 직접 시스템 명령 수행 불가
- **쓰기 액션 캐시 제외**: `search_logs`, `summarize_alerts`만 캐시 (대시보드 생성·편집은 캐시 안 함)
- **Langfuse 감사 로그**: 모든 LLM 호출 비용·레이턴시·툴 선택 기록

---

## 개발 환경 정보

- Python 3.11+
- Node.js 18+
- Docker Desktop
- OTel Java Agent v2.27.0
- OTel Collector Contrib v0.99.0
