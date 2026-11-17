#!/usr/bin/env bash
# =============================================================================
# Pravah Production Services Startup Script
# Target: Yotta Bare-Metal VM (Docker Compose + systemd)
#
# Usage:
#   chmod +x scripts/start_prod_services.sh
#   ./scripts/start_prod_services.sh [start|stop|restart|status|health]
#
# Managed by systemd unit: /etc/systemd/system/pravah.service
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$BACKEND_DIR/docker-compose.yml"
ENV_FILE="$BACKEND_DIR/environments/prod.env"
LOG_DIR="$BACKEND_DIR/logs/startup"
COMPOSE_PROJECT="pravah"

# Load production env
if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

mkdir -p "$LOG_DIR"
STARTUP_LOG="$LOG_DIR/startup-$(date +%Y%m%d-%H%M%S).log"

# ---- Logging helpers -------------------------------------------------------
log()    { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$STARTUP_LOG"; }
log_ok() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ✅ $*" | tee -a "$STARTUP_LOG"; }
log_err(){ echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ❌ $*" | tee -a "$STARTUP_LOG" >&2; }

# ---- Pre-flight checks ------------------------------------------------------
preflight() {
    log "Running pre-flight checks..."

    command -v docker &>/dev/null       || { log_err "docker not found"; exit 1; }
    command -v docker-compose &>/dev/null || \
        docker compose version &>/dev/null || { log_err "docker compose not found"; exit 1; }

    [[ -f "$COMPOSE_FILE" ]]   || { log_err "docker-compose.yml not found at $COMPOSE_FILE"; exit 1; }
    [[ -f "$ENV_FILE" ]]       || { log_err "prod.env not found at $ENV_FILE"; exit 1; }

    # Warn if any placeholder is still unset
    if grep -q "##SECRET\|##YOTTA_URL" "$ENV_FILE"; then
        log_err "WARNING: prod.env still contains unresolved ##SECRET## or ##YOTTA_URL## placeholders."
        log_err "         Replace them before deploying to production Yotta VM."
    fi

    log_ok "Pre-flight checks passed"
}

# ---- Compose wrapper --------------------------------------------------------
compose() {
    docker compose \
        -f "$COMPOSE_FILE" \
        --project-name "$COMPOSE_PROJECT" \
        --env-file "$ENV_FILE" \
        --profile prod \
        "$@"
}

# ---- Service startup with health-gate ---------------------------------------
wait_healthy() {
    local service="$1"
    local max_wait="${2:-120}"
    local interval=5
    local elapsed=0

    log "Waiting for [$service] to become healthy (max ${max_wait}s)..."
    while [[ $elapsed -lt $max_wait ]]; do
        local health
        health=$(docker inspect --format='{{.State.Health.Status}}' \
            "${COMPOSE_PROJECT}-${service}" 2>/dev/null || echo "missing")

        case "$health" in
            healthy)
                log_ok "$service is healthy"
                return 0
                ;;
            starting)
                sleep $interval
                elapsed=$((elapsed + interval))
                ;;
            unhealthy)
                log_err "$service is unhealthy — check: docker logs ${COMPOSE_PROJECT}-${service}"
                return 1
                ;;
            *)
                sleep $interval
                elapsed=$((elapsed + interval))
                ;;
        esac
    done
    log_err "$service health timeout after ${max_wait}s"
    return 1
}

# ---- Start ------------------------------------------------------------------
cmd_start() {
    log "============================================================"
    log "  Pravah Production Start"
    log "  $(date -u)"
    log "============================================================"

    preflight

    log "Pulling / building images..."
    compose build --pull --quiet 2>&1 | tee -a "$STARTUP_LOG"

    # Boot order: Redis → Control Plane → Decision Brain → Observer → Workers
    log "Starting Redis..."
    compose up -d redis
    wait_healthy "redis" 60

    log "Starting Control Plane (port 7000)..."
    compose up -d control-plane
    wait_healthy "control-plane" 120

    log "Starting Decision Brain (port 8000)..."
    compose up -d decision-brain
    wait_healthy "decision-brain" 120

    log "Starting Observer (port 8600)..."
    compose up -d observer
    wait_healthy "observer" 90

    log "Starting deploy workers..."
    compose up -d deploy-worker-1 deploy-worker-2 deploy-worker-3

    log "Starting monitoring services..."
    compose up -d queue-monitor health-monitor prometheus

    log ""
    log_ok "============================================================"
    log_ok "  Pravah Production Stack ONLINE"
    log_ok "  Control Plane : http://$(hostname -I | awk '{print $1}'):7000/api/health"
    log_ok "  Decision Brain: http://$(hostname -I | awk '{print $1}'):8000/health"
    log_ok "  Observer      : http://$(hostname -I | awk '{print $1}'):8600"
    log_ok "  Prometheus    : http://$(hostname -I | awk '{print $1}'):9090"
    log_ok "  Startup log   : $STARTUP_LOG"
    log_ok "============================================================"
}

# ---- Stop -------------------------------------------------------------------
cmd_stop() {
    log "Stopping Pravah production stack..."
    compose down --timeout 30
    log_ok "All services stopped"
}

# ---- Restart ----------------------------------------------------------------
cmd_restart() {
    cmd_stop
    sleep 3
    cmd_start
}

# ---- Status -----------------------------------------------------------------
cmd_status() {
    compose ps
}

# ---- Health -----------------------------------------------------------------
cmd_health() {
    log "Running production health validation..."
    python3 "$SCRIPT_DIR/validate_prod_health.py" \
        --env prod \
        --output "$BACKEND_DIR/deployment_verification_packet/prod_runtime_health.json"
    log_ok "Proof written to deployment_verification_packet/prod_runtime_health.json"
}

# ---- Logs -------------------------------------------------------------------
cmd_logs() {
    local service="${1:-}"
    if [[ -n "$service" ]]; then
        compose logs -f --tail=100 "$service"
    else
        compose logs -f --tail=50
    fi
}

# ---- Entrypoint -------------------------------------------------------------
case "${1:-start}" in
    start)   cmd_start   ;;
    stop)    cmd_stop    ;;
    restart) cmd_restart ;;
    status)  cmd_status  ;;
    health)  cmd_health  ;;
    logs)    cmd_logs "${2:-}" ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|health|logs [service]}"
        exit 1
        ;;
esac
