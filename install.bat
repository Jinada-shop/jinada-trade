@echo off
title Jinada.Trade - Setup

echo.
echo ============================================================
echo         Jinada.Trade - Automatic Setup
echo ============================================================
echo.

cd /d "%~dp0"
echo Working folder: %CD%
echo.

:: Check Python
echo [1/5] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version
echo [OK] Python found
echo.

:: Install libraries
echo [2/5] Installing libraries...
pip install --upgrade pip --quiet
pip install pandas numpy python-dotenv requests scikit-learn --quiet
pip install streamlit plotly mplfinance hmmlearn --quiet
pip install python-telegram-bot ccxt --quiet
echo [OK] Libraries installed
echo.

:: Create folders
echo [3/5] Creating folders...
mkdir models 2>nul
mkdir logs 2>nul
mkdir reports 2>nul
mkdir static 2>nul
echo [OK] Folders ready
echo.

:: Create .env if missing
echo [4/5] Checking .env...
if not exist ".env" (
    (
        echo # Telegram
        echo TELEGRAM_TOKEN=your_telegram_token
        echo TELEGRAM_CHAT_ID=your_chat_id
        echo.
        echo # Binance
        echo BINANCE_API_KEY=
        echo BINANCE_SECRET_KEY=
        echo.
        echo # Bybit
        echo BYBIT_API_KEY=
        echo BYBIT_SECRET_KEY=
        echo.
        echo # DeepSeek AI
        echo DEEPSEEK_API_KEY=
    ) > .env
    echo [OK] .env created - fill in your keys!
) else (
    echo [OK] .env exists
)
echo.

:: Create balance.txt if missing
if not exist "balance.txt" (
    echo 300.00 > balance.txt
    echo [OK] balance.txt created (300.00$)
)
echo.

:: Init database
echo [5/5] Initializing database...
python -c "from database import init_database; init_database(); print('Database ready')"
echo.

:: Done
echo ============================================================
echo         SETUP COMPLETE!
echo ============================================================
echo.
echo Choose launch mode:
echo   [1] Web Platform (Streamlit)
echo   [2] Trading Bot (Console)
echo   [3] Both (Web + Bot)
echo   [4] Exit
echo.
set /p MODE="Enter number (1-4): "

if "%MODE%"=="1" goto web
if "%MODE%"=="2" goto bot
if "%MODE%"=="3" goto both
if "%MODE%"=="4" goto end
goto end

:web
echo.
echo Starting Web Platform...
echo Open: http://localhost:8501
start "" http://localhost:8501
streamlit run web_app.py
goto end

:bot
echo.
echo Starting Trading Bot...
python main.py
goto end

:both
echo.
echo Starting Web + Bot...
start "Jinada-Web" cmd /c "streamlit run web_app.py --server.headless true"
timeout /t 3 >nul
start "Jinada-Bot" cmd /c "python main.py"
echo.
echo Web: http://localhost:8501
echo Bot: running in background
pause
goto end

:end
exit /b 0