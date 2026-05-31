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

echo Opening http://127.0.0.1:7860 when the server is ready...
start "" powershell -NoProfile -WindowStyle Hidden -Command "$url='http://127.0.0.1:7860'; for ($i=0; $i -lt 60; $i++) { try { $response = Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 2; if ($response.StatusCode -eq 200) { Start-Process $url; exit 0 } } catch { Start-Sleep -Seconds 1 } }; Start-Process $url"

call ".venv\Scripts\python.exe" app.py
