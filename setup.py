"""
Jinada.Trade - Python Setup Script
Run: python setup.py
"""

import os
import sys
import subprocess
from pathlib import Path

def print_step(step, text):
    print(f"\n{'='*60}")
    print(f"  [{step}] {text}")
    print(f"{'='*60}")

def check_python():
    print_step("1/6", "Checking Python")
    version = sys.version_info
    print(f"  Python {version.major}.{version.minor}.{version.micro}")
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("  [ERROR] Python 3.8+ required!")
        return False
    print("  [OK] Python version OK")
    return True

def install_packages():
    print_step("2/6", "Installing packages")
    packages = [
        "pandas", "numpy", "python-dotenv", "requests",
        "scikit-learn", "hmmlearn",
        "streamlit", "plotly", "mplfinance",
        "python-telegram-bot", "ccxt"
    ]
    
    for pkg in packages:
        print(f"  Installing {pkg}...")
        subprocess.run([sys.executable, "-m", "pip", "install", pkg, "--quiet"], check=True)
    
    print("  [OK] All packages installed")

def create_folders():
    print_step("3/6", "Creating folders")
    folders = ["models", "logs", "reports", "static"]
    for folder in folders:
        Path(folder).mkdir(exist_ok=True)
        print(f"  {folder}/ created")
    print("  [OK] Folders ready")

def create_env():
    print_step("4/6", "Checking .env file")
    env_path = Path(".env")
    if not env_path.exists():
        env_content = """# Telegram
TELEGRAM_TOKEN=your_telegram_token
TELEGRAM_CHAT_ID=your_chat_id

# Binance
BINANCE_API_KEY=
BINANCE_SECRET_KEY=

# Bybit
BYBIT_API_KEY=
BYBIT_SECRET_KEY=

# DeepSeek AI
DEEPSEEK_API_KEY=
"""
        env_path.write_text(env_content, encoding="utf-8")
        print("  [OK] .env created")
        print("  [WARNING] Fill in your API keys!")
    else:
        print("  [OK] .env already exists")

def create_balance():
    print_step("5/6", "Checking balance")
    balance_path = Path("balance.txt")
    if not balance_path.exists():
        balance_path.write_text("300.00")
        print("  [OK] balance.txt created ($300.00)")
    else:
        print("  [OK] balance.txt exists")

def init_database():
    print_step("6/6", "Initializing database")
    try:
        from database import init_database
        init_database()
        print("  [OK] Database ready")
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False
    return True

def show_menu():
    print(f"\n{'='*60}")
    print(f"  SETUP COMPLETE!")
    print(f"{'='*60}")
    print(f"\n  Choose launch mode:")
    print(f"    [1] Web Platform (http://localhost:8501)")
    print(f"    [2] Trading Bot (console)")
    print(f"    [3] Both (Web + Bot)")
    print(f"    [4] Exit")
    print()
    
    choice = input("  Enter number (1-4): ").strip()
    
    if choice == "1":
        print("\n  Starting Web Platform...")
        subprocess.run([sys.executable, "-m", "streamlit", "run", "web_app.py"])
    elif choice == "2":
        print("\n  Starting Trading Bot...")
        subprocess.run([sys.executable, "main.py"])
    elif choice == "3":
        print("\n  Starting Web + Bot...")
        # Start web in background
        subprocess.Popen([sys.executable, "-m", "streamlit", "run", "web_app.py"])
        print("  Web: http://localhost:8501")
        # Start bot
        subprocess.run([sys.executable, "main.py"])
    elif choice == "4":
        print("\n  Goodbye!")
    else:
        print("\n  Invalid choice")

if __name__ == "__main__":
    print()
    print("=" * 60)
    print("  Jinada.Trade - AI Trading Platform Setup")
    print("=" * 60)
    
    if not check_python():
        input("\nPress Enter to exit...")
        sys.exit(1)
    
    install_packages()
    create_folders()
    create_env()
    create_balance()
    
    if not init_database():
        input("\nPress Enter to exit...")
        sys.exit(1)
    
    show_menu()
    
    input("\nPress Enter to exit...")