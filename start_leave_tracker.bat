@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    where py >nul 2>nul
    if errorlevel 1 (
        python -m venv .venv
    ) else (
        py -m venv .venv
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo Python virtual environment could not be created.
    pause
    exit /b 1
)

if not exist ".venv\.requirements-installed" (
    echo Installing requirements...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Requirements could not be installed.
        pause
        exit /b 1
    )
    echo installed > ".venv\.requirements-installed"
)

echo Opening Izin Takip at http://127.0.0.1:8000
start "" "http://127.0.0.1:8000"
".venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8000

pause
