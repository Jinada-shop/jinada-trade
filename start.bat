@echo off
title Jinada.Trade - Full System
cd /d "%~dp0"

cls
echo.
echo ============================================================
echo         Jinada.Trade - Full System Launch
echo ============================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    pause
    exit
)

:: Check files
if not exist "jinada_server.py" (
    echo [ERROR] jinada_server.py not found!
    pause
    exit
)
if not exist "main.py" (
    echo [WARNING] main.py not found - bot will not trade
)

:: Install dependencies if needed
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo Installing Streamlit...
    pip install streamlit --quiet
)

:: Start Web Server
echo.
echo [1/2] Starting Web Server...
start "Jinada-Web" cmd /c "streamlit run jinada_server.py --server.port 8501"

:: Start Trading Bot
echo [2/2] Starting Trading Bot...
if exist "main.py" (
    start "Jinada-Bot" cmd /c "python main.py"
) else (
    echo Bot file not found - skipping
)

:: Wait for services
timeout /t 8 >nul

:: Show status
cls
echo.
echo ============================================================
echo         Jinada.Trade - ALL SERVICES RUNNING
echo ============================================================
echo.
echo   Web Platform:  http://localhost:8501
echo   Trading Bot:   Running in background
echo.
echo   Commands:
echo     Admin Panel:  python jinada_server.py admin
echo     Check stats:  python check_stats.py
echo.
echo ============================================================
echo.
echo   Services are running in separate windows.
echo   Close this window to EXIT.
echo   Close the other windows to stop services.
echo ============================================================
echo.
echo   Press any key to stop all services...
pause >nul

:: Stop all
taskkill /FI "WINDOWTITLE eq Jinada-Web*" /T >nul 2>&1
taskkill /FI "WINDOWTITLE eq Jinada-Bot*" /T >nul 2>&1
echo.
echo All services stopped.
timeout /t 2 >nul
exit