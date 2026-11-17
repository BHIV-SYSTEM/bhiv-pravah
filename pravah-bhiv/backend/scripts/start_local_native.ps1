$BackendDir = $PSScriptRoot + "\.."

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "    PRAVAH NATIVE STARTUP SCRIPT (WINDOWS LOCAL)       " -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan

# 0. Kill anything on ports 8600, 7000, 8000 to prevent conflicts
Write-Host "`n[0/7] Clearing ports 7000, 8000, 8600 of existing processes..." -ForegroundColor Yellow
foreach ($port in @(7000, 8000, 8600)) {
    netstat -ano | findstr ":$port " | ForEach-Object {
        $p = ($_ -split '\s+')[-1]
        if ($p -match '^\d+$' -and $p -ne '0') {
            taskkill /F /PID $p 2>&1 | Out-Null
        }
    }
}
Start-Sleep -Seconds 2
Write-Host "Ports cleared." -ForegroundColor DarkGray

# 1. Start Redis in Docker
Write-Host "`n[1/7] Starting Redis Event Bus via Docker Compose..." -ForegroundColor Yellow
Set-Location $BackendDir
docker compose -f docker-compose.yml --env-file environments/prod.env --profile prod up -d redis

Write-Host "Waiting 10 seconds for Redis to initialize..." -ForegroundColor DarkGray
Start-Sleep -Seconds 10

# Helper function to open a new terminal window, set all environment variables, and run a command
function Start-ServiceWindow {
    param(
        [string]$Title, 
        [string]$Command
    )
    
    # We must escape the $ variables with a backtick (`) so they evaluate in the NEW window, not the current one.
    $EnvSetup = "cd $BackendDir; .\\venv\\Scripts\\activate; `$env:PYTHONPATH='$BackendDir'; `$env:ENVIRONMENT='prod'; `$env:REDIS_HOST='127.0.0.1'; `$env:REDIS_PORT='6380'; `$env:LINEAGE_SIGNING_KEY='local-dummy-key'; `$env:SSPL_SECRET_KEY='local-dummy-key'; `$env:PRAVAH_TTG_API='https://ttg-backend-55ce.onrender.com'; `$env:PRAVAH_BHIV_KESHAV='https://keshav-cia7.onrender.com'; `$env:PRAVAH_WORKFLOW_BLACKHOLE_API='https://blackholeworkflow.onrender.com'; `$env:PRAVAH_CRM_API='https://ai-crm-4nje.onrender.com'; `$env:PRAVAH_HR_API='https://bhiv-hr-gateway-l0xp.onrender.com'; `$env:PRAVAH_BHIV_HR_AGENT='https://bhiv-hr-agent-cato.onrender.com'; `$env:PRAVAH_BHIV_HR_LANGGRAPH='https://bhiv-hr-langgraph-luy9.onrender.com'; `$env:PRAVAH_BHIV_BUCKET='https://bhiv-bucket-i1l6.onrender.com'; `$env:PRAVAH_PROMPT_RUNNER_API='https://prompt-runner.onrender.com'; `$env:PRAVAH_SHAKTI_GC_INFRA='https://shakti-gc-infra.onrender.com'; `$env:PRAVAH_BHIV_INSIGHT_CORE='https://tantra-core.onrender.com'; `$env:PRAVAH_BHIV_INSIGHT_FLOW_BACKEND='https://tantra-insightflow.onrender.com'; `$env:PRAVAH_BHIV_INSIGHT_FLOW_BRIDGE='https://tantra-gated-bridge-infrastructure.onrender.com'; `$env:PRAVAH_SAMRUDDHI_API='https://samruddhi.blackholeinfiverse.com/api'; `$env:PRAVAH_SAMRUDDHI_HFT='https://samruddhi.blackholeinfiverse.com/hft'; `$env:PRAVAH_GURUKUL_API='https://gurukul-up9j.onrender.com'; `$env:PRAVAH_MDU_API='https://bhiv-mdu-api.onrender.com'; `$env:PRAVAH_MITRA_API='https://bhiv-mitra.onrender.com'; `$env:PRAVAH_PARIKSHAK_API='http://parikshak.blackholeinfiverse.com/api/v1'; `$env:PRAVAH_INSIGHTBRIDGE_DEMO_API='https://insightbridge-phase-4-2-integration-demo.onrender.com'; `$env:PRAVAH_UNIGURU_API='https://uniguru-ai-2.onrender.com'; `$env:PRAVAH_BHIV_SARATHI='https://sarathi-9n5g.onrender.com'; `$env:PRAVAH_MASTERDB_API='https://masterdb-ingestion-certification-service.onrender.com'; `$env:PRAVAH_CORE_INTEGRATOR_API='https://core-integrator-collaborative.onrender.com';"
    
    $FullCommand = "$EnvSetup `$host.UI.RawUI.WindowTitle = '$Title'; clear; Write-Host '--- $Title ---' -ForegroundColor Green; Write-Host 'Press CTRL+C to stop this service.`n' -ForegroundColor DarkGray; $Command"
    
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $FullCommand
}

# 2. Control Plane
Write-Host "[2/7] Launching Control Plane (Port 7000)..." -ForegroundColor Yellow
Start-ServiceWindow -Title "PRAVAH Control Plane (7000)" -Command "python wsgi.py"
Start-Sleep -Seconds 2

# 3. Decision Brain
Write-Host "[3/7] Launching Decision Brain (Port 8000)..." -ForegroundColor Yellow
Start-ServiceWindow -Title "PRAVAH Decision Brain (8000)" -Command "uvicorn control_plane.backend.app.main:app --host 0.0.0.0 --port 8000 --log-level info"
Start-Sleep -Seconds 2

# 4. Observer Server — use 127.0.0.1 to avoid IPv6/Docker conflict on 0.0.0.0:8600
Write-Host "[4/7] Launching Observer Server (Port 8600)..." -ForegroundColor Yellow
Start-ServiceWindow -Title "PRAVAH Observer (8600)" -Command "uvicorn observer_server:app --host 127.0.0.1 --port 8600 --log-level info"
Start-Sleep -Seconds 2

# 5. Deploy Agent
Write-Host "[5/7] Launching Multi-Deploy Agent..." -ForegroundColor Yellow
Start-ServiceWindow -Title "PRAVAH Deploy Agent 1" -Command "`$env:WORKER_ID='1'; python -m control_plane.agents.multi_deploy_agent --env prod --workers 3"

# 6. Queue Monitor
Write-Host "[6/7] Launching Queue Monitor..." -ForegroundColor Yellow
Start-ServiceWindow -Title "PRAVAH Queue Monitor" -Command "python -m monitoring.queue_monitor --continuous --cycles 0"

# 7. Health Monitor
Write-Host "[7/7] Launching Health Monitor..." -ForegroundColor Yellow
Start-ServiceWindow -Title "PRAVAH Health Monitor" -Command "python -m monitoring.infra_health_monitor --env prod --continuous"

Write-Host "`n=======================================================" -ForegroundColor Cyan
Write-Host "  All services launched successfully in new windows!   " -ForegroundColor Green
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "`nDashboard: http://localhost:8600" -ForegroundColor Green
Write-Host "Control Plane: http://localhost:7000" -ForegroundColor Green
Write-Host "Decision Brain: http://localhost:8000" -ForegroundColor Green
