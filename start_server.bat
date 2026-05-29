@echo off
title Jinada.Trade Server
cd /d "%~dp0"

:menu
cls
echo.
echo ============================================================
echo         Jinada.Trade - Control Panel
echo ============================================================
echo.
echo   [1] Start Web Server
echo   [2] Start Trading Bot
echo   [3] Start All
echo   [4] Admin Panel
echo   [5] Exit
echo.
set /p choice="Choose [1-5]: "

if "%choice%"=="1" goto server
if "%choice%"=="2" goto bot
if "%choice%"=="3" goto all
if "%choice%"=="4" goto admin
if "%choice%"=="5" goto exit
goto menu

:server
cls
echo Starting Web Server...
echo Open: http://localhost:8501
streamlit run jinada_server.py --server.port 8501
goto menu

:bot
cls
echo Starting Bot...
python main.py
goto menu

:all
cls
echo Starting All...
start "Server" cmd /c "streamlit run jinada_server.py --server.port 8501"
timeout /t 3 >nul
start "Bot" cmd /c "python main.py"
echo Done! Web: http://localhost:8501
pause
goto menu

:admin
cls
echo Admin Panel...
python jinada_server.py admin
pause
goto menu

:exit
exit