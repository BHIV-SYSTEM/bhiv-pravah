#!/bin/bash

# ============================================================
# Pravah Automated Rollback Script
# Triggered when deployment fails
# ============================================================

set -e

DEPLOY_DIR="/opt/pravah"
BACKUP_DIR="/opt/pravah-backup"
LOG_FILE="/var/log/pravah-rollback.log"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "🔄 PRAVAH DEPLOYMENT ROLLBACK INITIATED"
log "=========================================="

# Check if backup exists
if [ ! -d "$BACKUP_DIR" ]; then
    log "❌ No backups found at $BACKUP_DIR"
    log "Cannot rollback without backup"
    exit 1
fi

# Get the latest backup
LATEST_BACKUP=$(ls -td "$BACKUP_DIR"/backup_* 2>/dev/null | head -n1)

if [ -z "$LATEST_BACKUP" ]; then
    log "❌ No valid backup found"
    exit 1
fi

log "📦 Found backup: $LATEST_BACKUP"

cd "$DEPLOY_DIR"

# Step 1: Stop current services
log "🛑 Stopping current services..."
docker compose down 2>&1 | tee -a "$LOG_FILE" || true

# Step 2: Remove current deployment
log "🗑️ Cleaning up current deployment..."
rm -rf "$DEPLOY_DIR"/* 2>&1 | tee -a "$LOG_FILE" || true

# Step 3: Restore from backup
log "📥 Restoring from backup..."
cp -r "$LATEST_BACKUP"/* "$DEPLOY_DIR"/ 2>&1 | tee -a "$LOG_FILE"

# Step 4: Start previous version
log "🚀 Starting services from backup..."
cd "$DEPLOY_DIR"
docker compose --profile prod up -d 2>&1 | tee -a "$LOG_FILE"

# Step 5: Wait for health checks
log "⏳ Waiting for services to stabilize..."
sleep 10

# Step 6: Verify rollback
log "✅ Verifying rollback..."
if docker compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    log "✅ Redis is running"
else
    log "❌ Redis failed to start"
    exit 1
fi

log "=========================================="
log "✅ ROLLBACK COMPLETED SUCCESSFULLY"
log "=========================================="
log "Services restored from: $LATEST_BACKUP"

# Send notification (optional - customize for your alerting system)
log "📧 Consider sending alert to ops team"

exit 0
