@echo off
setlocal
title iPhone ERP - Automated Setup & Launcher
cd /d "%~dp0"

echo ========================================================
echo [1/5] Checking Python Environment...
echo ========================================================
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to your system PATH!
    pause
    exit /b 1
)

echo ========================================================
echo [2/5] Setting up Virtual Environment (venv)...
echo ========================================================
if not exist venv (
    python -m venv venv
)

echo ========================================================
echo [3/5] Installing Dependencies Automatically...
echo ========================================================
call venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install Flask Flask-SQLAlchemy Werkzeug openpyxl pandas reportlab jinja2

echo ========================================================
echo [4/5] Preparing Local Folders and Database...
echo ========================================================
if not exist data mkdir data

echo ========================================================
echo Opening application in browser...
echo ========================================================
start "" http://127.0.0.1:5000
python app.py
pause


