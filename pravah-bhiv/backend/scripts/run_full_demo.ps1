Param(
    [switch]$TearDown
)

$ErrorActionPreference = 'Stop'

# Move to repo root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $scriptDir "..")

Write-Host "[DEMO] Starting services with docker-compose"
docker-compose up -d

if (Test-Path .\venv\Scripts\Activate.ps1) {
    Write-Host "[DEMO] Activating virtualenv"
    & .\.venv\Scripts\Activate.ps1
}

Write-Host "[DEMO] Running runtime flow"
python .\scripts\run_full_system_flow.py

Write-Host "[DEMO] Demo finished"

if ($TearDown) {
    Write-Host "[DEMO] Tearing down services"
    docker-compose down
}
#!/usr/bin/env pwsh

# Starting BHIV Pravah Execution Suite Demo
Write-Host "[*] Starting BHIV Pravah Execution Suite Demo..." -ForegroundColor Cyan

# ENV
$env:PYTHONPATH = "$PWD;$PWD\control_plane"
$env:ENVIRONMENT = "dev"
$env:CONTROL_PLANE_PORT = "7000"
$env:PYTHONIOENCODING = "utf-8"

# Start server
Write-Host "[*] Starting Control Plane API..." -ForegroundColor Cyan

$pythonPath = "$PWD\.venv\Scripts\python.exe"

if (-not (Test-Path $pythonPath)) {
    Write-Host "[ERROR] .venv Python not found" -ForegroundColor Red
    exit 1
}

$serverProcess = Start-Process -FilePath $pythonPath `
    -ArgumentList "control_plane/api/agent_api.py" `
    -NoNewWindow `
    -PassThru

if (-not $serverProcess) {
    Write-Host "[ERROR] Failed to start server" -ForegroundColor Red
    exit 1
}

$SERVER_PID = $serverProcess.Id
Write-Host "[OK] Server PID: $SERVER_PID" -ForegroundColor Green

# Wait for readiness
Write-Host "[*] Waiting for server to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 25
Write-Host "[OK] Server initialized" -ForegroundColor Green

$serverReady = $false
for ($i = 0; $i -lt 20; $i++) {
    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $tcpClient.Connect("127.0.0.1", 7000)
        $tcpClient.Close()
        $serverReady = $true
        Write-Host "[OK] Port 7000 is accepting connections" -ForegroundColor Green
        break
    } catch {
        Write-Host "[*] Waiting for port 7000..." -ForegroundColor Gray
        Start-Sleep -Seconds 1
    }
}

if (-not $serverReady) {
    Write-Host "[ERROR] Server did not open port 7000" -ForegroundColor Red
    Stop-Process -Id $SERVER_PID -Force -ErrorAction SilentlyContinue
    exit 1
}

# Trigger event
Write-Host "[*] Triggering runtime event..." -ForegroundColor Cyan

$body = @{
    app = "demo-app"
    env = "dev"
    state = "crashed"
    latency_ms = 300
    errors_last_min = 10
    workers = 2
} | ConvertTo-Json -Compress

$response = $null
for ($i = 0; $i -lt 10; $i++) {
    try {
        $response = Invoke-RestMethod `
            -Uri "http://localhost:7000/api/runtime" `
            -Method Post `
            -ContentType "application/json" `
            -Body $body `
            -TimeoutSec 10
        break
    } catch {
        Write-Host "[*] Runtime POST retry $($i + 1)/10..." -ForegroundColor Gray
        Start-Sleep -Seconds 2
    }
}

if (-not $response) {
    Write-Host "[ERROR] Runtime event failed after retries" -ForegroundColor Red
    Stop-Process -Id $SERVER_PID -Force -ErrorAction SilentlyContinue
    exit 1
}

Write-Host ""
$response | ConvertTo-Json -Depth 6
Write-Host ""

# Wait for logs
Start-Sleep -Seconds 2

Write-Host "[*] Check server logs above for:" -ForegroundColor Yellow
Write-Host "    - PRAVAH STREAM" -ForegroundColor Gray
Write-Host "    - ACT PHASE TRIGGERED" -ForegroundColor Gray
Write-Host ""

# Cleanup
Write-Host "[*] Stopping server (PID: $SERVER_PID)..." -ForegroundColor Yellow
Stop-Process -Id $SERVER_PID -Force -ErrorAction SilentlyContinue

Write-Host "[OK] Demo complete." -ForegroundColor Green