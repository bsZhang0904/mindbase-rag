@echo off
echo Starting MindBase...
echo.
echo [1/2] Make sure PostgreSQL is running (docker compose up -d)
echo [2/2] Starting backend and frontend...
echo.

start "MindBase Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\activate && uvicorn app.main:app --reload --port 8000"
timeout /t 3 /nobreak > nul
start "MindBase Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Backend: http://localhost:8000/docs
echo Frontend: http://localhost:5173
pause
