# start_presentation.ps1
# Automate launching the multi-agent control plane services and Next.js frontend

$ErrorActionPreference = 'Stop'

# 1. Environment Configurations
$env:PYTHONPATH = "$PWD;$PWD\control_plane"
$env:ENVIRONMENT = "dev"
$env:PYTHONIOENCODING = "utf-8"

$pythonPath = "$PWD\.venv\Scripts\python.exe"
if (-not (Test-Path $pythonPath)) {
    # Try parent virtual environment fallback
    $pythonPath = "$PWD\..\.venv\Scripts\python.exe"
}

if (-not (Test-Path $pythonPath)) {
    Write-Host "[ERROR] Virtual environment (.venv) python executor not found." -ForegroundColor Red
    Write-Host "Please ensure you have a .venv folder in the workspace." -ForegroundColor Yellow
    exit 1
}

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "           PRAVAH SYSTEM AUTOMATED PRESENTATION LAUNCHER" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

# 2. Start Target Web Application (web1) on port 5001
Write-Host "[*] Launching Target Application (web1) on port 5001..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:PYTHONPATH='$env:PYTHONPATH'; `$env:ENVIRONMENT='dev'; & '$pythonPath' reliability-controller2-main/web1/app.py" -NoNewWindow:$false

# 3. Start Rayyan Action Executor on port 5003
Write-Host "[*] Launching Rayyan Executor on port 5003..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:PYTHONPATH='$env:PYTHONPATH'; `$env:ENVIRONMENT='dev'; & '$pythonPath' reliability-controller2-main/executer/app.py" -NoNewWindow:$false

# 4. Start Telemetry Monitor Service on port 5004
Write-Host "[*] Launching Monitor Service on port 5004..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:PYTHONPATH='$env:PYTHONPATH'; `$env:ENVIRONMENT='dev'; & '$pythonPath' reliability-controller2-main/monitor/app.py" -NoNewWindow:$false

# 5. Start Control Plane Backend on port 8000
Write-Host "[*] Launching Control Plane Decision Brain on port 8000..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:PYTHONPATH='$env:PYTHONPATH'; `$env:ENVIRONMENT='dev'; & '$pythonPath' control_plane/backend/run.py" -NoNewWindow:$false

# 6. Start Next.js Frontend Dashboard on port 4500
Write-Host "[*] Launching Next.js UI Dashboard on port 4500..." -ForegroundColor Yellow
$frontendDir = Join-Path $PWD "dashboard\frontend"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$frontendDir'; npm run dev" -NoNewWindow:$false

# 7. Wait for services to bootstrap
Write-Host "[*] Waiting 6 seconds for services to initialize..." -ForegroundColor Green
Start-Sleep -Seconds 6

# 8. Open Web Browser tabs to show the visual status
Write-Host "[*] Opening browser tabs to Next.js Web UI & FastAPI Docs..." -ForegroundColor Green
Start-Process "http://localhost:4500"
Start-Sleep -Seconds 1
Start-Process "http://localhost:8000/docs"

# 9. Launch the interactive CLI presentation controller
Write-Host "\n[*] Running the Interactive Demo controller..." -ForegroundColor Cyan
& $pythonPath interactive_demo.py
