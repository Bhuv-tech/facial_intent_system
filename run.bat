@echo off
echo Starting Facial Intent System...

:: Start Backend in a new window
start cmd /k ".\venv\Scripts\python.exe -m uvicorn backend.api:app --host 0.0.0.0 --port 8000"

:: Start Frontend in a new window
cd frontend
start cmd /k "npx vite --host"

echo System is starting. 
echo Backend will be at http://localhost:8000
echo Frontend will be at https://localhost:5173/ (or check Vite terminal for network IP)
pause
