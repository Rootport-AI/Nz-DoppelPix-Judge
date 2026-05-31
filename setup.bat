@echo off
setlocal

cd /d "%~dp0"

echo.
echo [Nz DoppelPix Judge] Setup
echo.

set "PYTHON_CMD="
where py >nul 2>nul
if %errorlevel%==0 set "PYTHON_CMD=py -3"

if not defined PYTHON_CMD (
    where python >nul 2>nul
    if %errorlevel%==0 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo Python was not found.
    echo Install Python 3.10 or newer, then run setup.bat again.
    if not defined NZ_DOPPELPIX_NO_PAUSE pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    call %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo Failed to create .venv.
        if not defined NZ_DOPPELPIX_NO_PAUSE pause
        exit /b 1
    )
) else (
    echo Reusing existing .venv.
)

echo.
echo Installing core dependencies...
call ".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :install_failed

call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :install_failed

if /i "%~1"=="--core-only" goto :skip_optional
if /i "%NZ_DOPPELPIX_CORE_ONLY%"=="1" goto :skip_optional

echo.
echo Installing optional CLIP Score and ImageReward dependencies...
call ".venv\Scripts\python.exe" -m pip install -r requirements-optional.txt
if errorlevel 1 goto :install_failed
goto :done

:skip_optional
echo.
echo Skipping optional dependencies.
echo CLIP Score and ImageReward will be unavailable until requirements-optional.txt is installed.

:done
echo.
echo Setup complete.
echo Run run.bat to start the Web GUI.
if not defined NZ_DOPPELPIX_NO_PAUSE pause
exit /b 0

:install_failed
echo.
echo Setup failed while installing dependencies.
echo Check the error above, then run setup.bat again.
if not defined NZ_DOPPELPIX_NO_PAUSE pause
exit /b 1
