#!/bin/bash

# ============================================================
# Pravah Production VM Setup Script
# Run this ONCE on a fresh Ubuntu 22.04 VM
# ============================================================

set -e

echo "=========================================="
echo "🚀 PRAVAH VM SETUP"
echo "=========================================="

# Configuration
DEPLOY_DIR="/opt/pravah"
BACKUP_DIR="/opt/pravah-backup"
REPO_URL="$1"  # Pass as: https://github.com/your-org/your-repo.git

if [ -z "$REPO_URL" ]; then
    echo "Usage: $0 <github-repo-url>"
    echo "Example: $0 https://github.com/myorg/pravah.git"
    exit 1
fi

# Step 1: Update system
echo "📦 Updating system packages..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

# Step 2: Install Docker
echo "🐳 Installing Docker..."
sudo apt-get install -y -qq \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    apt-transport-https \
    software-properties-common

# Add Docker GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt-get update -qq
sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add current user to docker group (optional)
# sudo usermod -aG docker $USER

# Step 3: Install Docker Compose v1 (if needed)
echo "📦 Installing Docker Compose..."
sudo curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
docker-compose --version

# Step 4: Create deployment directory structure
echo "📁 Creating directory structure..."
sudo mkdir -p "$DEPLOY_DIR" "$BACKUP_DIR"
sudo chown -R $USER:$USER "$DEPLOY_DIR" "$BACKUP_DIR"

# Step 5: Clone repository (only backend folder needed)
echo "📥 Cloning repository..."
cd /tmp
git clone --depth 1 --filter=blob:none --sparse "$REPO_URL" pravah-repo
cd pravah-repo
git sparse-checkout set backend

# Step 6: Copy backend to deploy directory
echo "📋 Setting up deployment directory..."
cp -r backend/* "$DEPLOY_DIR/"
cd "$DEPLOY_DIR"

# Step 7: Create .env file from template
echo "📝 Creating environment file..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file with your production values:"
    echo "   sudo nano $DEPLOY_DIR/.env"
    echo ""
fi

# Step 8: Create logs and data directories
echo "📂 Creating log and data directories..."
mkdir -p logs logs/dev logs/stage logs/prod logs/dev/performance
mkdir -p data insightflow
chmod -R 755 logs data

# Step 9: Create monitoring directory (for prometheus.yml)
echo "📊 Setting up monitoring..."
mkdir -p monitoring
# Note: prometheus.yml should be in the repo, copy it if exists
[ -f monitoring/prometheus.yml ] && echo "✅ prometheus.yml found" || echo "⚠️  Create monitoring/prometheus.yml manually"

# Step 10: Install systemd services
echo "🔧 Installing systemd services..."
sudo cp pravah-compose.service /etc/systemd/system/
sudo cp pravah-compose-rollback.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/pravah-compose*.service
sudo systemctl daemon-reload

# Step 11: Make scripts executable
echo "🔐 Setting script permissions..."
chmod +x scripts/rollback.sh
chmod +x docker-healthcheck.sh 2>/dev/null || true

# Step 12: Start Docker service
echo "🐳 Starting Docker daemon..."
sudo systemctl enable docker
sudo systemctl start docker

# Step 13: Test Docker
echo "✅ Testing Docker setup..."
docker --version
docker compose --version

# Step 14: Build/pull images (optional - CI/CD will do this)
echo "📥 Pulling Docker images (this may take a few minutes)..."
docker compose pull --quiet || echo "⚠️  Could not pull images yet (set DOCKER_HUB_USERNAME in .env)"

echo ""
echo "=========================================="
echo "✅ VM SETUP COMPLETED"
echo "=========================================="
echo ""
echo "📋 NEXT STEPS:"
echo ""
echo "1. Edit environment variables:"
echo "   nano $DEPLOY_DIR/.env"
echo ""
echo "2. Review docker-compose.yml:"
echo "   cat $DEPLOY_DIR/docker-compose.yml"
echo ""
echo "3. Test manual start (optional):"
echo "   cd $DEPLOY_DIR"
echo "   docker compose --profile prod up -d"
echo ""
echo "4. Enable auto-start with systemd:"
echo "   sudo systemctl enable pravah-compose"
echo "   sudo systemctl start pravah-compose"
echo ""
echo "5. Check service status:"
echo "   sudo systemctl status pravah-compose"
echo "   docker compose ps"
echo ""
echo "6. View logs:"
echo "   docker compose logs -f control-plane"
echo "   journalctl -u pravah-compose -f"
echo ""
echo "=========================================="
