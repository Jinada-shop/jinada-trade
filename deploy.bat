@echo off
title Jinada.Trade - GitHub Deploy
cd /d "%~dp0"

cls
echo.
echo ============================================================
echo   Jinada.Trade - GitHub + Streamlit Cloud Deploy
echo ============================================================
echo.

:: Проверка Git
git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git not found!
    echo Download: https://git-scm.com/download/win
    pause
    exit
)

:: Запрос данных
echo.
echo Enter your GitHub username:
set /p GIT_USER="  Username: "
echo.
echo Enter repository name (default: jinada-trade):
set /p REPO_NAME="  Repo name: "
if "%REPO_NAME%"=="" set REPO_NAME=jinada-trade

:: Создание .gitignore
echo.
echo [1/5] Creating .gitignore...
(
    echo __pycache__/
    echo *.pyc
    echo .env
    echo balance.txt
    echo trading_bot.db
    echo models/
    echo logs/
    echo *.log
    echo clients.json
    echo .streamlit/
) > .gitignore
echo   Done.

:: Создание requirements.txt если нет
echo [2/5] Checking requirements.txt...
if not exist "requirements.txt" (
    echo streamlit > requirements.txt
    echo pandas >> requirements.txt
    echo plotly >> requirements.txt
    echo python-dotenv >> requirements.txt
    echo requests >> requirements.txt
    echo scikit-learn >> requirements.txt
    echo   Created.
) else (
    echo   Found.
)

:: Создание папки .streamlit с конфигом
echo [3/5] Creating Streamlit config...
mkdir .streamlit 2>nul
(
    echo [server]
    echo headless = true
    echo port = 8501
    echo enableCORS = false
    echo enableXsrfProtection = false
) > .streamlit\config.toml
echo   Done.

:: Инициализация Git
echo [4/5] Initializing Git...
git init
git add .
git commit -m "Jinada.Trade v5.0 - Initial deploy"
git branch -M main
echo   Done.

:: Создание репозитория через GitHub CLI или инструкция
echo [5/5] Ready to push!
echo.
echo ============================================================
echo   NEXT STEPS:
echo ============================================================
echo.
echo   1. Create repo on GitHub:
echo      https://github.com/new
echo      Name: %REPO_NAME%
echo      Make it PRIVATE
echo      DO NOT add README
echo.
echo   2. Run these commands in terminal:
echo.
echo      git remote add origin https://github.com/%GIT_USER%/%REPO_NAME%.git
echo      git push -u origin main
echo.
echo   3. Deploy on Streamlit Cloud:
echo      https://share.streamlit.io
echo      New app -> Your repo -> jinada_server.py
echo.
echo ============================================================
pause