# =============================================================================
# Pravah Production Services Startup — PowerShell
# Target: Windows (local production simulation / pre-Yotta validation)
#
# Usage (run as Administrator or in Docker context):
#   .\scripts\start_prod_services.ps1 [-Action start|stop|restart|status|health]
# =============================================================================

param(
    [ValidateSet("start", "stop", "restart", "status", "health", "logs")]
    [string]$Action = "start",
    [string]$Service = ""
)

$ErrorActionPreference = "Stop"

$ScriptDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir   = Split-Path -Parent $ScriptDir
$ComposeFile  = Join-Path $BackendDir "docker-compose.yml"
$EnvFile      = Join-Path $BackendDir "environments\prod.env"
$LogDir       = Join-Path $BackendDir "logs\startup"
$Project      = "pravah"

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
$StartupLog = Join-Path $LogDir "startup-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"

# ---- Logging helpers --------------------------------------------------------
function Log-Info  { param($msg) $line = "[$(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ')] $msg"; Write-Host $line; Add-Content $StartupLog $line }
function Log-OK    { param($msg) $line = "[$(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ')] ✅ $msg"; Write-Host $line -ForegroundColor Green; Add-Content $StartupLog $line }
function Log-Error { param($msg) $line = "[$(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ')] ❌ $msg"; Write-Host $line -ForegroundColor Red; Add-Content $StartupLog $line }

# ---- Docker Compose wrapper -------------------------------------------------
function Invoke-Compose {
    param([string[]]$Args)
    & docker compose `
        -f $ComposeFile `
        --project-name $Project `
        --env-file $EnvFile `
        --profile prod `
        @Args
    if ($LASTEXITCODE -ne 0) { throw "docker compose failed (exit $LASTEXITCODE)" }
}

# ---- Wait for container health ----------------------------------------------
function Wait-Healthy {
    param([string]$ContainerName, [int]$MaxWait = 120)
    $elapsed = 0
    Log-Info "Waiting for [$ContainerName] health (max ${MaxWait}s)..."
    while ($elapsed -lt $MaxWait) {
        try {
            $health = (docker inspect --format='{{.State.Health.Status}}' "${Project}-${ContainerName}" 2>$null)
            switch ($health) {
                "healthy"   { Log-OK "$ContainerName is healthy"; return }
                "unhealthy" { Log-Error "$ContainerName unhealthy - check: docker logs ${Project}-${ContainerName}"; throw "unhealthy" }
                default     { Start-Sleep 5; $elapsed += 5 }
            }
        } catch {
            Start-Sleep 5; $elapsed += 5
        }
    }
    Log-Error "$ContainerName health timeout after ${MaxWait}s"
    throw "timeout"
}

# ---- Pre-flight check -------------------------------------------------------
function Test-Preflight {
    Log-Info "Running pre-flight checks..."
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Log-Error "docker not found"; exit 1 }
    if (-not (Test-Path $ComposeFile)) { Log-Error "docker-compose.yml not found"; exit 1 }
    if (-not (Test-Path $EnvFile))     { Log-Error "prod.env not found"; exit 1 }
    if (Select-String -Path $EnvFile -Pattern "##SECRET|##YOTTA_URL" -Quiet) {
        Log-Error "WARNING: prod.env still contains ##SECRET## or ##YOTTA_URL## placeholders. Replace before deploying."
    }
    Log-OK "Pre-flight checks passed"
}

# ---- Start ------------------------------------------------------------------
function Start-Pravah {
    Log-Info "============================================================"
    Log-Info "  Pravah Production Start  $(Get-Date -Format 'u')"
    Log-Info "============================================================"
    Test-Preflight

    Log-Info "Building / pulling images..."
    Invoke-Compose @("build", "--pull", "--quiet")

    Log-Info "Starting Redis..."
    Invoke-Compose @("up", "-d", "redis")
    Wait-Healthy "redis" 60

    Log-Info "Starting Control Plane (port 7000)..."
    Invoke-Compose @("up", "-d", "control-plane")
    Wait-Healthy "control-plane" 120

    Log-Info "Starting Decision Brain (port 8000)..."
    Invoke-Compose @("up", "-d", "decision-brain")
    Wait-Healthy "decision-brain" 120

    Log-Info "Starting Observer (port 8600)..."
    Invoke-Compose @("up", "-d", "observer")
    Wait-Healthy "observer" 90

    Log-Info "Starting deploy workers..."
    Invoke-Compose @("up", "-d", "deploy-worker-1", "deploy-worker-2", "deploy-worker-3")

    Log-Info "Starting monitoring services..."
    Invoke-Compose @("up", "-d", "queue-monitor", "health-monitor", "prometheus")

    Log-OK "============================================================"
    Log-OK "  Pravah Production Stack ONLINE"
    Log-OK "  Control Plane : http://localhost:7000/api/health"
    Log-OK "  Decision Brain: http://localhost:8000/health"
    Log-OK "  Observer      : http://localhost:8600"
    Log-OK "  Prometheus    : http://localhost:9090"
    Log-OK "  Startup log   : $StartupLog"
    Log-OK "============================================================"
}

# ---- Stop -------------------------------------------------------------------
function Stop-Pravah {
    Log-Info "Stopping Pravah production stack..."
    Invoke-Compose @("down", "--timeout", "30")
    Log-OK "All services stopped"
}

# ---- Health -----------------------------------------------------------------
function Test-Health {
    Log-Info "Running production health validation..."
    $validatorPath = Join-Path $ScriptDir "validate_prod_health.py"
    $outputPath    = Join-Path $BackendDir "deployment_verification_packet\prod_runtime_health.json"
    python $validatorPath --env prod --output $outputPath
    if ($LASTEXITCODE -eq 0)  { Log-OK "All health checks PASSED - proof: $outputPath" }
    elseif ($LASTEXITCODE -eq 1) { Log-Error "PARTIAL failures - check: $outputPath" }
    else                       { Log-Error "CRITICAL failures - check: $outputPath"; exit 2 }
}

# ---- Entrypoint -------------------------------------------------------------
switch ($Action) {
    "start"   { Start-Pravah }
    "stop"    { Stop-Pravah }
    "restart" { Stop-Pravah; Start-Sleep 3; Start-Pravah }
    "status"  { Invoke-Compose @("ps") }
    "health"  { Test-Health }
    "logs"    {
        if ($Service) { Invoke-Compose @("logs", "-f", "--tail=100", $Service) }
        else          { Invoke-Compose @("logs", "-f", "--tail=50") }
    }
}
