@echo off
setlocal EnableDelayedExpansion

:: ── Console setup ────────────────────────────────────────────────────────────
title FALCON Controller Server

:: Enable ANSI escape codes (Windows 10+)
for /F %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"

:: ── Banner ───────────────────────────────────────────────────────────────────
echo.
echo %ESC%[96m======================================================%ESC%[0m
echo %ESC%[96m   FALCON Controller - One-Click Setup ^& Launch%ESC%[0m
echo %ESC%[96m======================================================%ESC%[0m
echo.

:: ── Step 1: Check Python ─────────────────────────────────────────────────────
echo %ESC%[1m[1/5] Checking Python installation...%ESC%[0m
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   %ESC%[91mX  Python is NOT installed or not in PATH!%ESC%[0m
    echo.
    echo   Please download and install Python 3.10+ from:
    echo   %ESC%[96mhttps://www.python.org/downloads/%ESC%[0m
    echo.
    echo   Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   %ESC%[92m√%ESC%[0m %PYVER% found
echo.

:: ── Step 2: Create / activate virtual environment ────────────────────────────
echo %ESC%[1m[2/5] Setting up Python virtual environment...%ESC%[0m
if not exist ".\venv\" (
    echo   Creating virtual environment in .\venv\ ...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo   %ESC%[91mX  Failed to create virtual environment!%ESC%[0m
        pause
        exit /b 1
    )
    echo   %ESC%[92m√%ESC%[0m Virtual environment created
) else (
    echo   %ESC%[92m√%ESC%[0m Virtual environment already exists
)

:: Activate venv
call .\venv\Scripts\activate.bat

:: Install dependencies
echo   Installing dependencies from requirements.txt...
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo   %ESC%[91mX  Failed to install dependencies!%ESC%[0m
    pause
    exit /b 1
)
echo   %ESC%[92m√%ESC%[0m Dependencies installed
echo.

:: ── Step 3: Check ViGEmBus driver ────────────────────────────────────────────
echo %ESC%[1m[3/5] Checking ViGEmBus driver...%ESC%[0m
python -c "import vgamepad; vgamepad.VX360Gamepad()" >nul 2>&1
if %errorlevel% neq 0 (
    echo   %ESC%[93m!  WARNING: ViGEmBus driver not detected or not working!%ESC%[0m
    echo.
    echo   The virtual gamepad requires the ViGEmBus driver.
    echo   Download it from:
    echo   %ESC%[96mhttps://github.com/nefarius/ViGEmBus/releases%ESC%[0m
    echo.
    echo   The server may fail to create a virtual gamepad without it.
    echo.
) else (
    echo   %ESC%[92m√%ESC%[0m ViGEmBus driver is active and working
    echo.
)

:: ── Step 4: Try ADB reverse tunnel ──────────────────────────────────────────
echo %ESC%[1m[4/5] Attempting ADB USB tunnel...%ESC%[0m
set "ADB_CMD=adb"
where adb >nul 2>&1
if %errorlevel% neq 0 (
    if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" (
        set "ADB_CMD=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
    )
)
"%ADB_CMD%" reverse tcp:9000 tcp:9000 >nul 2>&1
if %errorlevel% equ 0 (
    echo   %ESC%[92m√%ESC%[0m ADB reverse tunnel established on port 9000
) else (
    echo   %ESC%[93m-%ESC%[0m ADB not found or no device connected (skipped, not required)
)
echo.

:: ── Step 5: Launch the server ────────────────────────────────────────────────
echo %ESC%[1m[5/5] Launching FALCON Controller Server...%ESC%[0m
echo %ESC%[90m──────────────────────────────────────────────────────%ESC%[0m
echo.
python -u src/main.py


:: ── On exit ──────────────────────────────────────────────────────────────────
echo.
echo %ESC%[93m[AirSim Controller] Server has stopped.%ESC%[0m
echo.
pause
