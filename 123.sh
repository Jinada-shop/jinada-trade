@echo off
chcp 65001 >nul
title Jinada.Trade — Автоматическая установка

echo.
echo ╔══════════════════════════════════════════════╗
echo ║                                              ║
echo ║      ✦ Jinada.Trade — Установка ✦          ║
echo ║      AI Trading Platform v4.0               ║
echo ║                                              ║
echo ╚══════════════════════════════════════════════╝
echo.

:: ============================================================
:: ПРОВЕРКА ПАПКИ
:: ============================================================
cd /d "%~dp0"
echo 📁 Рабочая папка: %CD%
echo.

:: ============================================================
:: ПРОВЕРКА PYTHON
:: ============================================================
echo 🔍 Проверяю Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python не найден!
    echo.
    echo 📥 Скачай Python: https://www.python.org/downloads/
    echo ⚠️ При установке включи галочку "Add Python to PATH"
    pause
    exit /b 1
)
echo ✅ Python найден
echo.

:: ============================================================
:: СОЗДАНИЕ ПАПОК
:: ============================================================
echo 📁 Создаю папки...
mkdir models 2>nul
mkdir logs 2>nul
mkdir reports 2>nul
mkdir static 2>nul
echo ✅ Папки созданы
echo.

:: ============================================================
:: УСТАНОВКА БИБЛИОТЕК
:: ============================================================
echo 📦 Устанавливаю библиотеки...
echo.

pip install --upgrade pip

echo 📦 Основные зависимости...
pip install pandas numpy python-dotenv requests

echo 📦 Машинное обучение...
pip install scikit-learn hmmlearn

echo 📦 Графики и визуализация...
pip install streamlit plotly mplfinance

echo 📦 Telegram и API...
pip install python-telegram-bot ccxt

echo.
echo ✅ Библиотеки установлены
echo.

:: ============================================================
:: ПРОВЕРКА ФАЙЛОВ
:: ============================================================
echo 📋 Проверяю файлы...

set MISSING=0

if not exist "main.py" (
    echo ❌ main.py отсутствует
    set MISSING=1
)
if not exist "config.py" (
    echo ❌ config.py отсутствует
    set MISSING=1
)
if not exist "database.py" (
    echo ❌ database.py отсутствует
    set MISSING=1
)
if not exist "logger.py" (
    echo ❌ logger.py отсутствует
    set MISSING=1
)
if not exist "indicators.py" (
    echo ❌ indicators.py отсутствует
    set MISSING=1
)
if not exist "strategies.py" (
    echo ❌ strategies.py отсутствует
    set MISSING=1
)
if not exist "risk_manager.py" (
    echo ❌ risk_manager.py отсутствует
    set MISSING=1
)
if not exist "budget_manager.py" (
    echo ❌ budget_manager.py отсутствует
    set MISSING=1
)
if not exist "deep_ai_engine.py" (
    echo ❌ deep_ai_engine.py отсутствует
    set MISSING=1
)
if not exist "multi_exchange.py" (
    echo ❌ multi_exchange.py отсутствует
    set MISSING=1
)
if not exist "binance_client.py" (
    echo ❌ binance_client.py отсутствует
    set MISSING=1
)
if not exist "bybit_client.py" (
    echo ❌ bybit_client.py отсутствует
    set MISSING=1
)
if not exist "cache.py" (
    echo ❌ cache.py отсутствует
    set MISSING=1
)

if %MISSING%==1 (
    echo.
    echo ⚠️ Некоторые файлы отсутствуют!
    echo Убедись, что все файлы бота в этой папке.
    pause
    exit /b 1
)

echo ✅ Все файлы на месте
echo.

:: ============================================================
:: СОЗДАНИЕ .env ЕСЛИ НЕТ
:: ============================================================
if not exist ".env" (
    echo 📝 Создаю .env файл...
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
    echo ✅ .env создан
    echo ⚠️ Заполни .env своими ключами!
) else (
    echo ✅ .env уже существует
)
echo.

:: ============================================================
:: СОЗДАНИЕ BALANCE.TXT ЕСЛИ НЕТ
:: ============================================================
if not exist "balance.txt" (
    echo 300.00 > balance.txt
    echo ✅ balance.txt создан (300.00$)
) else (
    echo ✅ balance.txt уже существует
)
echo.

:: ============================================================
:: ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
:: ============================================================
echo 🗄 Инициализирую базу данных...
python -c "from database import init_database; init_database(); print('✅ База данных готова')"
echo.

:: ============================================================
:: ПРОВЕРКА TELEGRAM
:: ============================================================
echo 📱 Проверяю Telegram...
python -c "from dotenv import load_dotenv; import os; load_dotenv(); token=os.getenv('TELEGRAM_TOKEN'); print('✅ Токен найден' if token and token!='your_telegram_token' else '⚠️ Токен Telegram не настроен')"
echo.

:: ============================================================
:: ЗАПУСК
:: ============================================================
echo ╔══════════════════════════════════════════════╗
echo ║         УСТАНОВКА ЗАВЕРШЕНА!                ║
echo ╚══════════════════════════════════════════════╝
echo.
echo 📋 Что дальше:
echo.
echo 1. Заполни .env файл своими ключами
echo    - Telegram токен (получить у @BotFather)
echo    - Binance API ключи (из настроек биржи)
echo.
echo 2. Выбери режим запуска:
echo.
echo    [1] Запустить Web-платформу
echo    [2] Запустить бота (консоль)
echo    [3] Запустить бота + Web вместе
echo    [4] Выход
echo.
set /p MODE="Введи номер (1-4): "

if "%MODE%"=="1" goto web
if "%MODE%"=="2" goto bot
if "%MODE%"=="3" goto both
if "%MODE%"=="4" goto end
goto end

:web
echo.
echo 🟡 Запускаю Web-платформу...
echo.
echo Откроется в браузере: http://localhost:8501
echo.
start "" http://localhost:8501
streamlit run web_app.py
goto end

:bot
echo.
echo 🤖 Запускаю бота...
echo.
python main.py
goto end

:both
echo.
echo 🟡 Запускаю Web-платформу + Бота...
echo.
start "JinadaTrade-Web" cmd /c "streamlit run web_app.py"
timeout /t 3 >nul
start "JinadaTrade-Bot" cmd /c "python main.py"
echo.
echo ✅ Оба процесса запущены!
echo 📱 Web: http://localhost:8501
echo 🤖 Бот: работает в фоне
echo.
pause
goto end

:end
echo.
echo 👋 До встречи! Jinada.Trade
timeout /t 3 >nul
exit /b 0