#!/usr/bin/env bash
set -euo pipefail

# Run full demo on Linux / macOS
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[DEMO] Starting services with docker-compose"
docker-compose up -d

echo "[DEMO] Activating virtualenv (if present)"
if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

echo "[DEMO] Running runtime flow"
python scripts/run_full_system_flow.py

echo "[DEMO] Demo finished"
Write-Host "🚀 Starting BHIV Pravah Execution Suite Demo..." -ForegroundColor Green

# Step 1 — Set env
$env:PYTHONPATH = "$PWD;$PWD\control_plane"
$env:ENVIRONMENT = "dev"
$env:CONTROL_PLANE_PORT = "7000"

# Step 2 — Start server properly
Write-Host "📦 Starting Control Plane API..." -ForegroundColor Cyan

$serverProcess = Start-Process $pythonPath = "$PWD\.venv\Scripts\python.exe" `
    -ArgumentList "control_plane/api/agent_api.py" `
    -NoNewWindow `
    -PassThru

if (-not $serverProcess) {
    Write-Host "❌ Failed to start server" -ForegroundColor Red
    exit
}

$SERVER_PID = $serverProcess.Id
Write-Host "✅ Server PID: $SERVER_PID"

# Step 3 — Wait for readiness
Write-Host "⏳ Waiting for server..."

$ready = $false
for ($i = 0; $i -lt 10; $i++) {
    try {
        Invoke-RestMethod -Uri "http://localhost:7000/api/health" -TimeoutSec 1 | Out-Null
        $ready = $true
        break
    } catch {
        Start-Sleep -Seconds 1
    }
}

if (-not $ready) {
    Write-Host "❌ Server did not start" -ForegroundColor Red
    Stop-Process -Id $SERVER_PID -Force -ErrorAction SilentlyContinue
    exit
}

Write-Host "✅ Server is ready"

# Step 4 — Trigger event
Write-Host "⚡ Triggering runtime event..."

$body = @{
    app = "demo-app"
    env = "dev"
    state = "crashed"
    latency_ms = 300
    errors_last_min = 10
    workers = 2
} | ConvertTo-Json -Compress

$response = Invoke-RestMethod `
    -Uri "http://localhost:7000/api/runtime" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body

$response | ConvertTo-Json -Depth 6

# Step 5 — Wait for logs
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "📡 Check your terminal above for:"
Write-Host "   → 🚀 PRAVAH STREAM"
Write-Host "   → 🔥 ACT PHASE TRIGGERED"
Write-Host ""

# Step 6 — Cleanup
Write-Host "🛑 Stopping server..." -ForegroundColor Yellow
Stop-Process -Id $SERVER_PID -Force -ErrorAction SilentlyContinue

Write-Host "✅ Demo complete." -ForegroundColor Green








