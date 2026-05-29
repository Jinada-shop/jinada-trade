from dotenv import load_dotenv
import os

load_dotenv()

print("TELEGRAM_TOKEN:", os.getenv("TELEGRAM_TOKEN")[:20] + "...")
print("TELEGRAM_CHAT_ID:", os.getenv("TELEGRAM_CHAT_ID"))
print("BINANCE_API_KEY:", os.getenv("BINANCE_API_KEY")[:20] + "...")
print("BINANCE_SECRET_KEY:", os.getenv("BINANCE_SECRET_KEY")[:20] + "...")