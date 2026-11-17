@echo off
echo 🐳 Starting Multi-Agent CI/CD System...

REM Create required directories
if not exist logs mkdir logs
if not exist dataset mkdir dataset
if not exist insightflow mkdir insightflow

REM Build and start services
docker-compose up --build -d

echo ✅ Services started:
echo   📊 Dashboard: http://localhost:8501
echo   🌐 MCP API: http://localhost:8080
echo   🤖 Agents: Running in background
echo.
echo 📋 Useful commands:
echo   docker-compose logs -f        # View all logs
echo   docker-compose logs agents    # View agent logs
echo   docker-compose down           # Stop all services