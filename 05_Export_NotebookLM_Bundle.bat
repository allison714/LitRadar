@echo off
title [05] LitRadar - Export NotebookLM Bundle by Date
cd /d "%~dp0"

if not exist "lab_config.env" (
    echo ==============================================================================
    echo [NOTE] 'lab_config.env' not found! Launching First-Time Setup Wizard...
    echo ==============================================================================
    echo.
    call "00_First_Time_Setup.bat"
)

echo ====================================================================
echo   LitRadar - Zotero Date Inspector and NotebookLM Exporter
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

if not defined PY_EXE (
    if exist "%USERPROFILE%\anaconda3\python.exe" set "PY_EXE=%USERPROFILE%\anaconda3\python.exe"
    if exist "%USERPROFILE%\miniconda3\python.exe" set "PY_EXE=%USERPROFILE%\miniconda3\python.exe"
    if exist "C:\ProgramData\anaconda3\python.exe" set "PY_EXE=C:\ProgramData\anaconda3\python.exe"
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
)

if not defined PY_EXE (
    where python >nul 2>nul
    if %errorlevel% equ 0 set "PY_EXE=python"
)

if not defined PY_EXE (
    echo [ERROR] No Python environment detected!
    echo Please install Python or Anaconda to run LitRadar.
    pause
    exit /b 1
)

"%PY_EXE%" core\export_lm_bundle.py
