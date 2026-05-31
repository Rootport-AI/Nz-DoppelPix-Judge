@echo off
setlocal

cd /d "%~dp0"

echo.
echo [Nz DoppelPix Judge] Starting
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment was not found. Running setup first...
    call "%~dp0setup.bat"
    if errorlevel 1 exit /b 1
)

echo Opening http://127.0.0.1:7860
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 4; Start-Process 'http://127.0.0.1:7860'"

call ".venv\Scripts\python.exe" app.py
