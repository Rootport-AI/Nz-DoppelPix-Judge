@echo off
setlocal

cd /d "%~dp0"

echo.
echo [Nz DoppelPix Judge] Starting
echo.

set "APP_URL=http://127.0.0.1:7870"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment was not found. Running setup first...
    call "%~dp0setup.bat"
    if errorlevel 1 exit /b 1
)

echo Opening %APP_URL% when the server is ready...
start "" powershell -NoProfile -WindowStyle Hidden -Command "$url='%APP_URL%'; for ($i=0; $i -lt 60; $i++) { try { $response = Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 2; if ($response.StatusCode -eq 200) { Start-Process $url; exit 0 } } catch { Start-Sleep -Seconds 1 } }; Start-Process $url"

call ".venv\Scripts\python.exe" app.py --listen
