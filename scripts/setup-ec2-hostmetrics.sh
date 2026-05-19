#!/bin/bash
# EC2에서 실행: OTel Collector로 Host Metrics를 ngrok → 로컬 Prometheus로 push
#
# 사용법:
#   NGROK_URL=https://<your-ngrok-url> bash setup-ec2-hostmetrics.sh
#
# 로컬 ngrok URL 확인:
#   curl http://localhost:4040/api/tunnels | jq '.tunnels[0].public_url'

set -euo pipefail

OTEL_VERSION="0.99.0"
OTEL_DIR="/opt/otel-hostmetrics"
CONFIG_PATH="${OTEL_DIR}/otel-collector-ec2-hostmetrics.yml"
SERVICE_NAME="otel-hostmetrics"

if [ -z "${NGROK_URL:-}" ]; then
  echo "❌ NGROK_URL 환경변수가 필요합니다."
  echo "   예: NGROK_URL=https://xxxx.ngrok-free.app bash $0"
  exit 1
fi

echo "=== OTel Collector (Host Metrics) 설치 ==="
echo "  ngrok URL : ${NGROK_URL}"
echo "  설치 경로  : ${OTEL_DIR}"
echo ""

# ── 바이너리 다운로드 ────────────────────────────────────────────────
sudo mkdir -p "${OTEL_DIR}"

if [ ! -f "${OTEL_DIR}/otelcol-contrib" ]; then
  echo "[1/4] OTel Collector 다운로드..."
  ARCH=$(uname -m)
  if [ "${ARCH}" = "x86_64" ]; then ARCH_NAME="amd64"; else ARCH_NAME="arm64"; fi
  DOWNLOAD_URL="https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v${OTEL_VERSION}/otelcol-contrib_${OTEL_VERSION}_linux_${ARCH_NAME}.tar.gz"
  curl -sL "${DOWNLOAD_URL}" -o /tmp/otelcol.tar.gz
  sudo tar -xzf /tmp/otelcol.tar.gz -C "${OTEL_DIR}" otelcol-contrib
  sudo chmod +x "${OTEL_DIR}/otelcol-contrib"
  echo "  → 완료"
else
  echo "[1/4] 이미 설치됨, 건너뜀"
fi

# ── 설정 파일 생성 ───────────────────────────────────────────────────
echo "[2/4] 설정 파일 생성..."
sudo tee "${CONFIG_PATH}" > /dev/null << 'YAML'
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
      processes: {}

processors:
  batch:
    timeout: 10s
  resource:
    attributes:
      - key: service.name
        value: "ec2-host"
        action: upsert
      - key: host.environment
        value: "production"
        action: upsert

exporters:
  otlphttp:
    endpoint: "NGROK_PLACEHOLDER"
    tls:
      insecure: false

service:
  pipelines:
    metrics:
      receivers: [hostmetrics]
      processors: [resource, batch]
      exporters: [otlphttp]
YAML

# ngrok URL 치환
sudo sed -i "s|NGROK_PLACEHOLDER|${NGROK_URL}|g" "${CONFIG_PATH}"
echo "  → 완료"

# ── systemd 서비스 등록 ──────────────────────────────────────────────
echo "[3/4] systemd 서비스 등록..."
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << EOF
[Unit]
Description=OTel Collector - EC2 Host Metrics
After=network.target

[Service]
ExecStart=${OTEL_DIR}/otelcol-contrib --config=${CONFIG_PATH}
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl restart ${SERVICE_NAME}
echo "  → 완료"

# ── 상태 확인 ───────────────────────────────────────────────────────
echo "[4/4] 서비스 상태 확인..."
sleep 3
sudo systemctl status ${SERVICE_NAME} --no-pager -l | head -20

echo ""
echo "✅ 완료! 30초 후 Prometheus에서 확인:"
echo "   curl 'http://localhost:9090/api/v1/query?query=otel_system_cpu_utilization_ratio'"
