"""
Автопостинг сигналов в Telegram канал
"""

import asyncio
from telegram import Bot
from config import config
from database import get_db
from datetime import datetime

async def post_stats():
    bot = Bot(token=config.TELEGRAM_TOKEN)
    
    with get_db() as db:
        total = db.execute("SELECT COUNT(*) FROM trades WHERE status='CLOSED'").fetchone()[0]
        wins = db.execute("SELECT COUNT(*) FROM trades WHERE status='CLOSED' AND pnl>0").fetchone()[0]
        pnl = db.execute("SELECT SUM(pnl) FROM trades WHERE status='CLOSED'").fetchone()[0] or 0
        today = db.execute("SELECT COUNT(*), SUM(pnl) FROM trades WHERE status='CLOSED' AND date(exit_time)=date('now')").fetchone()
    
    wr = (wins/total*100) if total > 0 else 0
    
    text = f"""📊 Jinada.Trade — Статистика
━━━━━━━━━━━━━━━━━━━━
🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}

💰 Всего сделок: {total}
🎯 Винрейт: {wr:.1f}%
💵 Общий PnL: {pnl:+.2f}$

📈 Сегодня:
• Сделок: {today[0] or 0}
• PnL: {today[1] or 0:+.2f}$

🤖 Бот работает 24/7
👉 @JinadaTradeBot
"""
    
    await bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=text)
    print("Posted!")

asyncio.run(post_stats())