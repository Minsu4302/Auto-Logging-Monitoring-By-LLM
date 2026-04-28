"""
외부 서비스 연동 가이드 자동 생성.
service_type × integration_method 조합별 OTel 설정 템플릿을 반환한다.
"""


def generate_integration_guide(
    service_name: str,
    service_type: str,
    integration_method: str,
    ngrok_url: str,
    environment: str = "production",
) -> str:
    method = integration_method or "otel-sdk"

    if method == "otel-sdk":
        if service_type == "aws-lambda":
            return _lambda_otel_guide(service_name, ngrok_url, environment)
        return _otel_sdk_guide(service_name, ngrok_url, environment, service_type)

    if method == "prometheus-exporter":
        return _prometheus_exporter_guide(service_name, ngrok_url, environment)

    if method == "fluent-bit":
        return _fluent_bit_guide(service_name, ngrok_url, environment)

    return _otel_sdk_guide(service_name, ngrok_url, environment, service_type)


# ─────────────────────────────────────────────────────────────────
# OTel SDK 가이드 (Spring Boot / Node.js / Python 공통)
# ─────────────────────────────────────────────────────────────────

def _otel_sdk_guide(
    service_name: str,
    ngrok_url: str,
    environment: str,
    service_type: str = "aws-ec2",
) -> str:
    return f"""## {service_name} — OTel SDK 연동 가이드 ({service_type})

ngrok 터널을 통해 로컬 OTel Collector로 데이터를 Push합니다.
**ngrok URL (재기동 시 변경됨):** `{ngrok_url}`

---

### Spring Boot (Java)

**1. pom.xml 의존성 추가**
```xml
<dependency>
    <groupId>io.opentelemetry.instrumentation</groupId>
    <artifactId>opentelemetry-spring-boot-starter</artifactId>
    <version>2.4.0</version>
</dependency>
```

**2. application.yml**
```yaml
otel:
  exporter:
    otlp:
      endpoint: {ngrok_url}
  service:
    name: {service_name}
  resource:
    attributes:
      env: {environment}
```

**3. EC2 환경변수 (application.yml 대신 사용 가능)**
```bash
export OTEL_EXPORTER_OTLP_ENDPOINT={ngrok_url}
export OTEL_SERVICE_NAME={service_name}
export OTEL_RESOURCE_ATTRIBUTES=env={environment}
```

---

### Node.js (Express / NestJS)

**1. 패키지 설치**
```bash
npm install @opentelemetry/sdk-node \\
            @opentelemetry/auto-instrumentations-node \\
            @opentelemetry/exporter-trace-otlp-http
```

**2. tracing.js (앱 진입점보다 먼저 import)**
```javascript
const {{ NodeSDK }} = require('@opentelemetry/sdk-node');
const {{ OTLPTraceExporter }} = require('@opentelemetry/exporter-trace-otlp-http');
const {{ getNodeAutoInstrumentations }} = require('@opentelemetry/auto-instrumentations-node');

const sdk = new NodeSDK({{
  traceExporter: new OTLPTraceExporter({{
    url: '{ngrok_url}/v1/traces',
  }}),
  instrumentations: [getNodeAutoInstrumentations()],
  serviceName: '{service_name}',
}});
sdk.start();
```

**3. 실행**
```bash
OTEL_RESOURCE_ATTRIBUTES=env={environment} node -r ./tracing.js app.js
```

---

### Python (FastAPI / Django)

**1. 패키지 설치**
```bash
pip install opentelemetry-sdk \\
            opentelemetry-exporter-otlp \\
            opentelemetry-instrumentation-fastapi
```

**2. 설정**
```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="{ngrok_url}/v1/traces"))
)
trace.set_tracer_provider(provider)
```

**3. 환경변수 방식**
```bash
export OTEL_EXPORTER_OTLP_ENDPOINT={ngrok_url}
export OTEL_SERVICE_NAME={service_name}
export OTEL_RESOURCE_ATTRIBUTES=env={environment}
opentelemetry-instrument uvicorn main:app
```

---

### 연동 확인
- Grafana → Explore → Tempo 데이터소스에서 `{service_name}` 트레이스 검색
- Grafana → Explore → Elasticsearch에서 `service.name: {service_name}` 로그 검색
"""


# ─────────────────────────────────────────────────────────────────
# AWS Lambda OTel Layer 가이드
# ─────────────────────────────────────────────────────────────────

def _lambda_otel_guide(service_name: str, ngrok_url: str, environment: str) -> str:
    return f"""## {service_name} — AWS Lambda OTel 연동 가이드

**ngrok URL:** `{ngrok_url}`

---

### Lambda Layer 추가

AWS 콘솔 또는 SAM/CDK에서 AWS 관리형 OTel Lambda Layer를 추가합니다.

**Layer ARN (us-east-1, x86_64 기준)**
```
arn:aws:lambda:us-east-1:901920570463:layer:aws-otel-collector-amd64-ver-0-90-1:1
```

### 환경변수 설정 (Lambda 콘솔 → 구성 → 환경 변수)
```
AWS_LAMBDA_EXEC_WRAPPER       = /opt/otel-handler
OPENTELEMETRY_COLLECTOR_CONFIG_FILE = /var/task/collector.yml
OTEL_SERVICE_NAME             = {service_name}
OTEL_RESOURCE_ATTRIBUTES      = env={environment}
```

### collector.yml (Lambda 배포 패키지에 포함)
```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

exporters:
  otlp:
    endpoint: {ngrok_url.replace("https://", "")}:443
    tls:
      insecure: false

service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [otlp]
```

### 연동 확인
- CloudWatch Logs에서 `[OTLP]` 프리픽스 로그 확인
- Grafana Tempo에서 Lambda 트레이스 확인
"""


# ─────────────────────────────────────────────────────────────────
# Prometheus Exporter 가이드 (EC2 직접 스크레이핑 — 방화벽 열린 경우)
# ─────────────────────────────────────────────────────────────────

def _prometheus_exporter_guide(service_name: str, ngrok_url: str, environment: str) -> str:
    return f"""## {service_name} — Prometheus Exporter 연동 가이드

> ⚠️ Pull 방식은 AWS Security Group에서 로컬 IP를 허용해야 합니다.
> 방화벽이 막혀 있으면 OTel SDK Push 방식 사용을 권장합니다.

---

### Spring Boot Actuator + Micrometer

**1. pom.xml**
```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-actuator</artifactId>
</dependency>
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-registry-prometheus</artifactId>
</dependency>
```

**2. application.yml**
```yaml
management:
  endpoints:
    web:
      exposure:
        include: prometheus,health
  metrics:
    tags:
      service: {service_name}
      env: {environment}
```

**3. prometheus.yml에 scrape_config 추가**
```yaml
- job_name: '{service_name}'
  static_configs:
    - targets: ['<EC2_PUBLIC_IP>:8080']
  metrics_path: '/actuator/prometheus'
  labels:
    environment: {environment}
```

### 연동 확인
- Prometheus UI → Targets에서 `{service_name}` 상태 UP 확인
"""


# ─────────────────────────────────────────────────────────────────
# Fluent Bit 가이드 (로그 Push)
# ─────────────────────────────────────────────────────────────────

def _fluent_bit_guide(service_name: str, ngrok_url: str, environment: str) -> str:
    return f"""## {service_name} — Fluent Bit 로그 연동 가이드

**ngrok URL (OTel HTTP):** `{ngrok_url}`

---

### EC2/ECS에 Fluent Bit 설치 및 설정

**fluent-bit.conf**
```ini
[SERVICE]
    Flush        5
    Log_Level    info

[INPUT]
    Name         tail
    Path         /var/log/{service_name}/*.log
    Tag          {service_name}.*
    Parser       json

[FILTER]
    Name         record_modifier
    Match        *
    Record       service_name {service_name}
    Record       environment  {environment}

[OUTPUT]
    Name         opentelemetry
    Match        *
    Host         {ngrok_url.replace("https://", "").split(":")[0]}
    Port         443
    Logs_uri     /v1/logs
    tls          on
    tls.verify   off
```

### Docker 사이드카 방식 (ECS)
```json
{{
  "name": "fluent-bit",
  "image": "fluent/fluent-bit:3.0",
  "volumesFrom": [],
  "mountPoints": [
    {{
      "sourceVolume": "logs",
      "containerPath": "/var/log/{service_name}"
    }}
  ],
  "environment": [
    {{"name": "SERVICE_NAME", "value": "{service_name}"}},
    {{"name": "NGROK_URL", "value": "{ngrok_url}"}}
  ]
}}
```

### 연동 확인
- Elasticsearch에서 `service_name: {service_name}` 인덱스 확인
- Kibana → Discover에서 로그 검색
"""
