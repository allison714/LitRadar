@echo off
title [02] LitRadar - Interactive Zotero Library Retagger and Topic Filter
cd /d "%~dp0"

if not exist "lab_config.env" (
    echo ==============================================================================
    echo [NOTE] 'lab_config.env' not found! Launching First-Time Setup Wizard...
    echo ==============================================================================
    echo.
    call "00_First_Time_Setup.bat"
)

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

"%PY_EXE%" core\retag_zotero_library.py

pause
