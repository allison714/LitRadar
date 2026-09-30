@echo off
title [06] LitRadar - Generate Weekly Slide Deck
cd /d "%~dp0"

if not exist "lab_config.env" (
    echo ==============================================================================
    echo [NOTE] 'lab_config.env' not found! Launching First-Time Setup Wizard...
    echo ==============================================================================
    echo.
    call "00_First_Time_Setup.bat"
)

echo ====================================================================
echo   LitRadar - Generating Weekly LM Slide Deck and Presentation
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
    pause
    exit /b 1
)

"%PY_EXE%" -c "
import sys
sys.path.insert(0, 'core')
from harvester import MultiEngineHarvester
from zotero_sync import ZoteroSync
from classifier import LiteratureClassifier
from slide_generator import SlideDeckGenerator

print('Collecting recent literature across 5 pillars...')
h = MultiEngineHarvester()
raw = h.harvest_all_tracks(days_back=30, max_results_per_track=15)
z = ZoteroSync()
clf = LiteratureClassifier()
harvested = {}
for k, papers in raw.items():
    filtered = z.filter_new_papers(papers)
    tagged = clf.classify_and_tag(k, filtered)
    if tagged:
        harvested[k] = tagged

gen = SlideDeckGenerator()
deck_path = gen.generate_slide_deck(harvested)
print('Opening slide deck in browser...')
import os
os.startfile(str(deck_path))
"
pause
