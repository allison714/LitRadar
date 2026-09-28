@echo off
title LitRadar - Setup Weekly Windows Task
cd /d "%~dp0"

if not exist "lab_config.env" (
    echo ==============================================================================
    echo [NOTE] 'lab_config.env' not found! Launching First-Time Setup Wizard...
    echo ==============================================================================
    echo.
    call "00_First_Time_Setup.bat"
)

echo ====================================================================
echo   LitRadar - Windows Task Scheduler
echo   Automated Surveillance (Every Sunday @ 11:00 PM)
echo ====================================================================
echo.

set "PY_EXE="
if exist "lab_config.env" (
    for /f "tokens=1,* delims==" %%A in ('findstr /v "^#" "lab_config.env"') do (
        if /i "%%A"=="PYTHON_EXE" (
            if exist "%%~B" set "PY_EXE=%%~B"
        )
    )
)

if not defined PY_EXE if exist "%USERPROFILE%\anaconda3\python.exe" set "PY_EXE=%USERPROFILE%\anaconda3\python.exe"
if not defined PY_EXE if exist "%USERPROFILE%\miniconda3\python.exe" set "PY_EXE=%USERPROFILE%\miniconda3\python.exe"
if not defined PY_EXE (
    where python >nul 2>nul
    if %errorlevel% equ 0 set "PY_EXE=python"
)

set TASK_NAME=LitRadar_Weekly_Surveillance
set SCRIPT_PATH=%~dp0core\main.py

echo Registering Task: %TASK_NAME%
echo Python Path:     "%PY_EXE%"
echo Target Script:   "%SCRIPT_PATH%"
echo.

schtasks /create /tn "%TASK_NAME%" /tr "\"%PY_EXE%\" \"%SCRIPT_PATH%\" --days 7" /sc weekly /d SUN /st 23:00 /f

if %errorlevel% equ 0 (
    echo.
    echo [SUCCESS] Task successfully scheduled!
    echo It will execute autonomously every Sunday at 11:00 PM.
) else (
    echo.
    echo [NOTE] If permission was denied, right-click this .bat file and select 'Run as Administrator'.
)

echo.
pause
