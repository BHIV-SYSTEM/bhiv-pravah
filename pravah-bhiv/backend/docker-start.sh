#!/bin/bash

echo "🐳 Starting Multi-Agent CI/CD System..."

# Create required directories
mkdir -p logs dataset insightflow

# Build and start services
docker-compose up --build -d

echo "✅ Services started:"
echo "  📊 Dashboard: http://localhost:8501"
echo "  🌐 MCP API: http://localhost:8080"
echo "  🤖 Agents: Running in background"

echo ""
echo "📋 Useful commands:"
echo "  docker-compose logs -f        # View all logs"
echo "  docker-compose logs agents    # View agent logs"
echo "  docker-compose down           # Stop all services"