# tunnel-prod.ps1
# EC2 Prod 서버 SSH 접속 헬퍼
#
# OTel Push 아키텍처에서 이 스크립트의 역할:
#   - EC2에 SSH 접속하여 OTel SDK 환경변수 확인/설정
#   - ngrok URL 변경 후 Prod 앱에 새 엔드포인트 적용할 때 사용
#
# 데이터 흐름: EC2 앱 → ngrok → 로컬 OTel Collector (이 스크립트와 무관)
#
# 사용법:
#   .\scripts\tunnel-prod.ps1              # EC2에 SSH 접속 (interactive)
#   .\scripts\tunnel-prod.ps1 -CheckOtel   # EC2의 OTel 환경변수 현황 출력
#   .\scripts\tunnel-prod.ps1 -SetOtel "https://<ngrok-url>"  # OTel 엔드포인트 업데이트

param(
    [switch]$CheckOtel,
    [string]$SetOtel = ""
)

$PemFile    = "magambell-monitor.pem"
$RemoteHost = "ubuntu@3.39.195.122"

# ── PEM 파일 위치 탐색 ──────────────────────────────────────────────
$PemPath = $null
$Candidates = @(
    (Join-Path $PSScriptRoot "..\$PemFile"),
    (Join-Path $HOME "$PemFile"),
    (Join-Path $HOME ".ssh\$PemFile"),
    (Join-Path (Get-Location) $PemFile)
)
foreach ($c in $Candidates) {
    if (Test-Path $c) { $PemPath = (Resolve-Path $c).Path; break }
}
if (-not $PemPath) {
    Write-Error "PEM 파일을 찾을 수 없습니다: $PemFile`n위치: $($Candidates -join ', ')"
    exit 1
}

$SshBase = "ssh -i `"$PemPath`" -o StrictHostKeyChecking=no $RemoteHost"

# ── OTel 환경변수 확인 ─────────────────────────────────────────────
if ($CheckOtel) {
    Write-Host "=== EC2 OTel 환경변수 확인 ===" -ForegroundColor Cyan
    $cmd = "printenv | grep -E 'OTEL_|JAVA_TOOL_OPTIONS' || echo '(설정된 OTel 환경변수 없음)'"
    Invoke-Expression "$SshBase `"$cmd`""
    exit 0
}

# ── OTel 엔드포인트 업데이트 ───────────────────────────────────────
if ($SetOtel) {
    Write-Host "=== EC2 OTel 엔드포인트 업데이트 ===" -ForegroundColor Cyan
    Write-Host "  새 ngrok URL: $SetOtel"
    Write-Host ""
    Write-Host "아래 환경변수를 EC2의 앱 프로세스 설정에 적용하세요:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  export OTEL_EXPORTER_OTLP_ENDPOINT=$SetOtel"
    Write-Host "  export OTEL_SERVICE_NAME=magambell-prod"
    Write-Host "  export OTEL_RESOURCE_ATTRIBUTES=env=production,deployment=blue"
    Write-Host ""
    Write-Host "적용 후 앱 재시작이 필요합니다."

    $confirm = Read-Host "EC2에 SSH 접속하여 직접 설정하시겠습니까? (y/N)"
    if ($confirm -eq "y" -or $confirm -eq "Y") {
        Invoke-Expression $SshBase
    }
    exit 0
}

# ── 기본: interactive SSH 접속 ────────────────────────────────────
Write-Host "=== EC2 Prod 서버 SSH 접속 ===" -ForegroundColor Cyan
Write-Host "  Host: $RemoteHost"
Write-Host "  PEM : $PemPath"
Write-Host ""
Write-Host "접속 후 OTel 설정 예시:"
Write-Host "  export OTEL_EXPORTER_OTLP_ENDPOINT=<ngrok-url>"
Write-Host "  export OTEL_SERVICE_NAME=magambell-prod"
Write-Host "  export OTEL_RESOURCE_ATTRIBUTES=env=production"
Write-Host ""
Invoke-Expression $SshBase
