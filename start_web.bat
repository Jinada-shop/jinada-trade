@echo off
title Jinada.Trade - Web Platform
cd /d "%~dp0"

echo.
echo ============================================================
echo   Jinada.Trade - Web Platform Launcher
echo ============================================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    pause
    exit
)

:: Install Streamlit if needed
echo [1/3] Checking Streamlit...
pip show streamlit >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing Streamlit...
    pip install streamlit --quiet
)

:: Check web_app.py exists
echo [2/3] Checking web_app.py...
if not exist "web_app.py" (
    echo Creating web_app.py...
    (
        echo import streamlit as st
        echo.
        echo st.set_page_config(page_title="Jinada.Trade", page_icon="🟡", layout="wide")
        echo.
        echo st.markdown("""
        echo ^<div style="text-align: center; padding: 50px;"^>
        echo     ^<h1 style="color: #FFD700;"^>Jinada.Trade^</h1^>
        echo     ^<p style="color: white; font-size: 20px;"^>AI Trading Platform^</p^>
        echo     ^<p style="color: #B8942E;"^>Status: Online^</p^>
        echo ^</div^>
        echo """, unsafe_allow_html=True)
        echo.
        echo st.success("Platform is running!")
        echo st.info("Open http://localhost:8501 in your browser")
    ) > web_app.py
    echo Done.
)

:: Launch
echo [3/3] Starting Web Platform...
echo.
echo ============================================================
echo   Platform starting...
echo   Open: http://localhost:8501
echo   Press Ctrl+C to stop
echo ============================================================
echo.

start "" http://localhost:8501
timeout /t 2 >nul
streamlit run web_app.py --server.port 8501 --server.headless false

pause