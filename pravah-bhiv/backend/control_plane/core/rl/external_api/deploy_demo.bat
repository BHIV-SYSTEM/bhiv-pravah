@echo off
echo ========================================
echo RL Decision Brain - Demo Deployment
echo ========================================

echo.
echo [1/4] Installing dependencies...
pip install -r requirements.txt

echo.
echo [2/4] Running validation tests...
python demo_validation.py

echo.
echo [3/4] Starting Demo API...
echo API will be available at: http://localhost:5000
echo Use API endpoints directly for validation
echo.
echo Press Ctrl+C to stop the API server
echo.

python demo_api.py