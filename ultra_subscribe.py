"""
Файл: ultra_subscribe.py
ULTRA SCALPING — 3 ДНЯ БЕСПЛАТНО, ПОТОМ ПОДПИСКА 9.99$/МЕС
"""

import asyncio
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import requests
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

print("\n" + "=" * 60)
print("   ⚡ ULTRA SCALPING BOT")
print("   3 дня бесплатно | Потом 9.99$/мес")
print("=" * 60 + "\n")

TELEGRAM_TOKEN = input("Токен Telegram бота: ").strip()
BINANCE_API_KEY = input("Binance API Key: ").strip()
BINANCE_SECRET_KEY = input("Binance Secret Key: ").strip()
BUDGET = float(input("Бюджет на скальпинг (USDT, например 50): ") or "50")

# ================================================================
# СИСТЕМА ПОДПИСКИ
# ================================================================

class SubscribeSystem:
    """Управление подписками."""
    
    def __init__(self):
        self.file = Path("subscribers.json")
        self.data = self._load()
    
    def _load(self) -> Dict:
        if self.file.exists():
            with open(self.file, 'r') as f:
                return json.load(f)
        return {"users": {}, "keys": {}}
    
    def _save(self):
        with open(self.file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def check_access(self, user_id: int) -> Dict:
        """Проверить доступ."""
        user_id = str(user_id)
        now = datetime.now()
        
        # Новый пользователь — пробный период 3 дня
        if user_id not in self.data["users"]:
            self.data["users"][user_id] = {
                "trial_start": now.isoformat(),
                "trial_end": (now + timedelta(days=3)).isoformat(),
                "subscribed": False,
                "subscription_end": None,
                "plan": "trial",
            }
            self._save()
            return {
                "access": True,
                "plan": "trial",
                "days_left": 3,
                "message": "🆓 Пробный период 3 дня"
            }
        
        user = self.data["users"][user_id]
        
        # Проверяем подписку
        if user.get("subscribed") and user.get("subscription_end"):
            sub_end = datetime.fromisoformat(user["subscription_end"])
            if now < sub_end:
                days_left = (sub_end - now).days
                return {
                    "access": True,
                    "plan": user.get("plan", "basic"),
                    "days_left": days_left,
                    "message": f"✅ Подписка активна"
                }
        
        # Проверяем пробный период
        if user.get("trial_end"):
            trial_end = datetime.fromisoformat(user["trial_end"])
            if now < trial_end:
                days_left = (trial_end - now).days
                return {
                    "access": True,
                    "plan": "trial",
                    "days_left": days_left,
                    "message": f"🆓 Пробный период"
                }
        
        # Доступ закончился
        return {
            "access": False,
            "plan": "none",
            "days_left": 0,
            "message": "🔴 Подписка закончилась. /subscribe"
        }
    
    def add_subscription(self, user_id: int, months: int = 1) -> bool:
        """Добавить подписку на N месяцев."""
        user_id = str(user_id)
        
        if user_id not in self.data["users"]:
            self.data["users"][user_id] = {}
        
        now = datetime.now()
        user = self.data["users"][user_id]
        
        # Если уже есть активная подписка — продлеваем
        if user.get("subscribed") and user.get("subscription_end"):
            current_end = datetime.fromisoformat(user["subscription_end"])
            if current_end > now:
                new_end = current_end + timedelta(days=30 * months)
            else:
                new_end = now + timedelta(days=30 * months)
        else:
            new_end = now + timedelta(days=30 * months)
        
        self.data["users"][user_id].update({
            "subscribed": True,
            "subscription_end": new_end.isoformat(),
            "plan": "basic",
        })
        self._save()
        
        return True
    
    def generate_key(self, months: int = 1) -> str:
        """Сгенерировать ключ пополнения."""
        key = f"US-{uuid.uuid4().hex[:8].upper()}"
        self.data["keys"][key] = {
            "months": months,
            "created_at": datetime.now().isoformat(),
            "used": False,
        }
        self._save()
        return key
    
    def use_key(self, user_id: int, key: str) -> Dict:
        """Использовать ключ."""
        user_id = str(user_id)
        
        if key not in self.data["keys"]:
            return {"status": "error", "message": "❌ Ключ не найден"}
        
        key_data = self.data["keys"][key]
        if key_data["used"]:
            return {"status": "error", "message": "❌ Ключ уже использован"}
        
        # Активируем подписку
        self.data["keys"][key]["used"] = True
        self.data["keys"][key]["used_by"] = user_id
        self.add_subscription(int(user_id), key_data["months"])
        self._save()
        
        return {
            "status": "success",
            "months": key_data["months"],
            "message": f"✅ Подписка продлена на {key_data['months']} мес!"
        }
    
    def generate_keys(self, months: int, count: int) -> list:
        """Создать несколько ключей."""
        keys = []
        for _ in range(count):
            key = self.generate_key(months)
            keys.append(key)
        return keys


# ================================================================
# BINANCE КЛИЕНТ
# ================================================================

class BinanceClient:
    BASE_URL = "https://api.binance.com"
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def _sign(self, params: dict) -> str:
        query = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        return hmac.new(self.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    
    def _request(self, method: str, path: str, params: dict = None, signed: bool = False):
        if params is None: params = {}
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["signature"] = self._sign(params)
        headers = {"X-MBX-APIKEY": self.api_key} if signed else {}
        url = f"{self.BASE_URL}{path}"
        resp = requests.get(url, params=params, headers=headers, timeout=10) if method == "GET" else requests.post(url, params=params, headers=headers, timeout=10)
        return resp.json()
    
    def get_price(self, symbol: str = "BTCUSDT") -> Optional[float]:
        try: return float(self._request("GET", "/api/v3/ticker/price", {"symbol": symbol})["price"])
        except: return None
    
    def get_balance(self) -> float:
        try:
            data = self._request("GET", "/api/v3/account", signed=True)
            for b in data.get("balances", []):
                if b["asset"] == "USDT": return float(b["free"])
        except: pass
        return BUDGET
    
    def market_buy(self, symbol: str, quantity: float) -> Optional[Dict]:
        try: return self._request("POST", "/api/v3/order", {"symbol": symbol, "side": "BUY", "type": "MARKET", "quantity": round(quantity, 6)}, signed=True)
        except: return None
    
    def market_sell(self, symbol: str, quantity: float) -> Optional[Dict]:
        try: return self._request("POST", "/api/v3/order", {"symbol": symbol, "side": "SELL", "type": "MARKET", "quantity": round(quantity, 6)}, signed=True)
        except: return None


# ================================================================
# ULTRA SCALPING
# ================================================================

class UltraScalping:
    def __init__(self, client: BinanceClient):
        self.client = client
        self.total_trades = 0
        self.total_profit = 0.0
        self.running = False
        self.paused = False
        self.balance = BUDGET
    
    async def get_btc_price(self) -> Optional[float]:
        return await asyncio.get_event_loop().run_in_executor(None, self.client.get_price)
    
    async def execute_trade(self):
        if self.paused: return
        price = await self.get_btc_price()
        if not price: return
        trade_amount = self.balance * 0.05
        quantity = trade_amount / price
        if quantity * price < 10: quantity = 10 / price
        
        loop = asyncio.get_event_loop()
        buy_result = await loop.run_in_executor(None, self.client.market_buy, "BTCUSDT", quantity)
        if not buy_result or "orderId" not in buy_result: return
        await asyncio.sleep(1)
        price = await self.get_btc_price() or price
        sell_result = await loop.run_in_executor(None, self.client.market_sell, "BTCUSDT", quantity)
        if not sell_result or "orderId" not in sell_result: return
        
        fill_price = float(buy_result.get("fills", [{}])[0].get("price", price))
        sell_price = float(sell_result.get("fills", [{}])[0].get("price", fill_price))
        profit = quantity * (sell_price - fill_price)
        
        self.total_trades += 1
        self.total_profit += profit
        
        if self.total_trades % 10 == 0:
            print(f"📊 Сделок: {self.total_trades} | Прибыль: {self.total_profit:+.4f}$")
    
    async def run_loop(self):
        self.running = True
        print(f"⚡ Ultra Scalping запущен!")
        while self.running:
            try:
                if not self.paused: await self.execute_trade()
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Ошибка: {e}")
                await asyncio.sleep(5)
    
    def get_stats(self) -> str:
        return (
            f"📊 <b>ULTRA SCALPING</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Бюджет: {BUDGET:.0f}$\n"
            f"📈 Сделок: {self.total_trades}\n"
            f"💵 Прибыль: {self.total_profit:+.4f}$\n"
            f"⏸ Статус: {'Пауза' if self.paused else 'Работает'}\n"
        )


# ================================================================
# TELEGRAM БОТ
# ================================================================

sub_sys = SubscribeSystem()
us = None


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global us
    user_id = update.effective_user.id
    username = update.effective_user.username or "User"
    
    access = sub_sys.check_access(user_id)
    
    if not access["access"]:
        await update.message.reply_text(
            f"🔴 <b>ДОСТУП ЗАКОНЧИЛСЯ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{access['message']}\n\n"
            f"<b>Продлите подписку:</b>\n"
            f"/subscribe — 9.99$/мес\n"
            f"/activate КЛЮЧ — Активировать ключ",
            parse_mode="HTML"
        )
        return
    
    if us is None:
        client = BinanceClient(BINANCE_API_KEY, BINANCE_SECRET_KEY)
        us = UltraScalping(client)
        asyncio.create_task(us.run_loop())
    
    emoji = "✅" if access["plan"] != "trial" else "🆓"
    text = (
        f"⚡ <b>ULTRA SCALPING BOT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 @{username}\n"
        f"{emoji} {access['message']}\n"
        f"⏳ Дней: {access['days_left']}\n\n"
        f"<b>Команды:</b>\n"
        f"/stats — Статистика\n"
        f"/pause /resume — Управление\n"
        f"/subscribe — Подписка 9.99$/мес\n"
        f"/activate КЛЮЧ — Активировать ключ"
    )
    
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if us is None:
        await update.message.reply_text("❌ /start сначала")
        return
    
    access = sub_sys.check_access(update.effective_user.id)
    if not access["access"]:
        await update.message.reply_text("❌ Подписка закончилась. /subscribe")
        return
    
    await update.message.reply_text(us.get_stats(), parse_mode="HTML")


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if us: us.paused = True
    await update.message.reply_text("⏸ Пауза")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if us: us.paused = False
    await update.message.reply_text("▶️ Работаем")


async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💎 <b>ПОДПИСКА — 9.99$/МЕС</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 <b>Как оплатить:</b>\n"
        "1️⃣ Переведите 9.99$ в USDT (TRC20):\n"
        "   <code>TВАШ_USDT_АДРЕС</code>\n"
        "2️⃣ Напишите админу: @your_username\n"
        "3️⃣ Пришлите скриншот оплаты\n"
        "4️⃣ Получите ключ активации\n"
        "5️⃣ Активируйте: /activate КЛЮЧ\n\n"
        "💬 @your_username",
        parse_mode="HTML"
    )


async def cmd_activate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text("❌ /activate КЛЮЧ")
        return
    
    key = context.args[0].upper()
    result = sub_sys.use_key(user_id, key)
    
    await update.message.reply_text(result["message"])


async def cmd_genkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создать ключи (админ)."""
    ADMIN_ID = 123456789  # ЗАМЕНИТЕ
    
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Нет доступа")
        return
    
    months = int(context.args[0]) if context.args else 1
    count = int(context.args[1]) if len(context.args) > 1 else 5
    
    keys = sub_sys.generate_keys(months, count)
    
    text = f"🔑 <b>СОЗДАНО {count} КЛЮЧЕЙ ({months} мес):</b>\n\n"
    for i, key in enumerate(keys, 1):
        text += f"{i}. <code>{key}</code>\n"
    
    await update.message.reply_text(text, parse_mode="HTML")


async def main():
    # Binance
    client = BinanceClient(BINANCE_API_KEY, BINANCE_SECRET_KEY)
    price = client.get_price()
    
    if not price:
        print("❌ Ошибка Binance!")
        return
    
    print(f"✅ Binance подключён! BTC: {price:.2f}$")
    
    # Ключи
    if not Path("subscribers.json").exists():
        keys = sub_sys.generate_keys(1, 10)
        print(f"🔑 Создано 10 ключей для продажи!")
    
    # Telegram
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("subscribe", cmd_subscribe))
    app.add_handler(CommandHandler("activate", cmd_activate))
    app.add_handler(CommandHandler("genkey", cmd_genkey))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    print("🤖 Бот запущен!")
    print("=" * 50)
    
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())