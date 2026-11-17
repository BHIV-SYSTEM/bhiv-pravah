#!/bin/bash
# Start script for Render deployment

echo "🚀 Starting Multi-Agent API Server on Render..."
echo "📍 Environment: ${ENV:-stage}"
echo "🔒 Demo Mode: ${DEMO_MODE:-true}"
echo "🧊 Freeze Mode: ${DEMO_FREEZE_MODE:-true}"

# Start Flask API
python api/agent_api.py
