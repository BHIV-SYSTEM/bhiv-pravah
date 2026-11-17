#!/bin/bash
# Docker Health Check Script for CI/CD System

set -e

# Function to check service health
check_service() {
    local service_name=$1
    local health_url=$2
    
    echo "Checking $service_name..."
    
    if curl -f -s "$health_url" > /dev/null 2>&1; then
        echo "✅ $service_name is healthy"
        return 0
    else
        echo "❌ $service_name is unhealthy"
        return 1
    fi
}

# Function to check file existence
check_file() {
    local file_path=$1
    local description=$2
    
    if [ -f "$file_path" ]; then
        echo "✅ $description exists"
        return 0
    else
        echo "❌ $description missing"
        return 1
    fi
}

echo "🏥 Docker Health Check Starting..."

# Check if we're inside a container
if [ -f /.dockerenv ]; then
    echo "Running inside Docker container"
    
    # Check based on container type
    if [ "$CONTAINER_TYPE" = "dashboard" ]; then
        check_service "Streamlit Dashboard" "http://localhost:8501/_stcore/health"
    elif [ "$CONTAINER_TYPE" = "mcp" ]; then
        check_service "MCP Endpoints" "http://localhost:8080/health"
    elif [ "$CONTAINER_TYPE" = "agents" ]; then
        check_file "/app/logs/deployment_log.csv" "Deployment log"
    else
        # Generic health check
        echo "✅ Container is running"
    fi
else
    echo "Running on host system"
    
    # Check Docker daemon
    if docker info > /dev/null 2>&1; then
        echo "✅ Docker daemon is running"
    else
        echo "❌ Docker daemon is not accessible"
        exit 1
    fi
    
    # Check containers
    echo "Checking container status..."
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
fi

echo "🎉 Health check completed"