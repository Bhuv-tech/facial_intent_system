@echo off
echo ==========================================
echo Starting Facial Intent System in Docker...
echo ==========================================
echo.
echo Building unified frontend/backend container...
echo.
docker compose up --build
echo.
echo Container stopped.
pause
