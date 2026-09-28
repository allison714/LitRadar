@echo off
title [00] LitRadar - First-Time Member Setup
cd /d "%~dp0"

echo ==============================================================================
echo                              LitRadar SUITE
echo                      FIRST-TIME MEMBER SETUP WIZARD
echo ==============================================================================
echo.

set "PY_EXE="

REM 1. Check if Python is specified in lab_config.env
if exist "lab_config.env" (
    for /f "tokens=1,* delims==" %%A in ('findstr /v "^#" "lab_config.env"') do (
        if /i "%%A"=="PYTHON_EXE" (
            if exist "%%~B" set "PY_EXE=%%~B"
        )
    )
)

REM 2. Auto-detect common Python installations
if not defined PY_EXE if exist "%USERPROFILE%\anaconda3\python.exe" set "PY_EXE=%USERPROFILE%\anaconda3\python.exe"
if not defined PY_EXE if exist "%USERPROFILE%\miniconda3\python.exe" set "PY_EXE=%USERPROFILE%\miniconda3\python.exe"
if not defined PY_EXE if exist "C:\ProgramData\anaconda3\python.exe" set "PY_EXE=C:\ProgramData\anaconda3\python.exe"
if not defined PY_EXE if exist "C:\ProgramData\miniconda3\python.exe" set "PY_EXE=C:\ProgramData\miniconda3\python.exe"
if not defined PY_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PY_EXE (
    where python >nul 2>nul
    if %errorlevel% equ 0 set "PY_EXE=python"
)

REM 3. If Python still not found, prompt the user
if not defined PY_EXE (
    echo [WARNING] Python could not be automatically located on this system.
    echo Please enter the full path to python.exe
    set /p "PY_EXE=Enter Python Path = "
)

if not defined PY_EXE (
    echo [ERROR] No Python path provided. Please install Anaconda or Python 3.10+ and re-run.
    pause
    exit /b 1
)

echo [INFO] Launching Setup Wizard using: "%PY_EXE%"
echo.

"%PY_EXE%" core\setup_wizard.py

echo.
pause
