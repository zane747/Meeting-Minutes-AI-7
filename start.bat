@echo off
title Meeting Minutes AI

echo ============================================
echo   Meeting Minutes AI - Starting...
echo ============================================
echo.

cd /d "C:\zriil\code\Meeting Minutes AI"

tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul
if errorlevel 1 (
    echo [1/3] Starting Ollama...
    start "" "C:\Users\zriil\AppData\Local\Programs\Ollama\ollama.exe" serve
    timeout /t 3 /nobreak >nul
) else (
    echo [1/3] Ollama already running
)

echo [2/3] Opening browser in 3 seconds...
start "" cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8000"

echo [3/3] Starting FastAPI server...
echo.
echo ============================================
echo   Running at: http://localhost:8000
echo   Press Ctrl+C to stop
echo ============================================
echo.
"C:\Users\zriil\.local\bin\uv.exe" run uvicorn app.main:app --host 0.0.0.0 --port 8000

echo.
echo Server stopped. Press any key to close...
pause >nul
