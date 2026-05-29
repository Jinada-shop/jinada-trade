"""
Файл: check_stats.py — Анализ статистики торговли
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("trading_bot.db")

if not DB_PATH.exists():
    print("❌ Файл trading_bot.db не найден!")
    print(f"   Ищу в: {DB_PATH.absolute()}")
    exit(1)

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=" * 60)
print("   📊 АНАЛИЗ ТОРГОВОЙ СТАТИСТИКИ")
print("=" * 60)

# 1. Общая статистика
print("\n" + "=" * 60)
print("1. ОБЩАЯ СТАТИСТИКА")
print("=" * 60)

cursor.execute("""
    SELECT 
        COUNT(*) as total_trades,
        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
        ROUND(SUM(pnl), 2) as total_pnl,
        ROUND(AVG(pnl), 4) as avg_pnl,
        ROUND(MAX(pnl), 4) as best_trade,
        ROUND(MIN(pnl), 4) as worst_trade
    FROM trades 
    WHERE status = 'CLOSED'
""")
row = cursor.fetchone()
if row and row['total_trades']:
    total = row['total_trades']
    wins = row['wins']
    wr = (wins / total * 100) if total > 0 else 0
    print(f"   Всего сделок: {total}")
    print(f"   Прибыльных: {wins}")
    print(f"   Винрейт: {wr:.1f}%")
    print(f"   Общий PnL: {row['total_pnl']}$")
    print(f"   Средний PnL: {row['avg_pnl']}$")
    print(f"   Лучшая сделка: {row['best_trade']}$")
    print(f"   Худшая сделка: {row['worst_trade']}$")
else:
    print("   Нет данных!")

# 2. По стратегиям
print("\n" + "=" * 60)
print("2. ПО СТРАТЕГИЯМ")
print("=" * 60)

cursor.execute("""
    SELECT 
        strategy,
        COUNT(*) as trades,
        ROUND(SUM(pnl), 2) as total_pnl,
        ROUND(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as winrate,
        ROUND(AVG(pnl), 4) as avg_pnl
    FROM trades 
    WHERE status = 'CLOSED' AND strategy != ''
    GROUP BY strategy
    ORDER BY total_pnl DESC
""")
rows = cursor.fetchall()
if rows:
    for r in rows:
        emoji = "🟢" if (r['total_pnl'] or 0) > 0 else "🔴"
        print(f"   {emoji} {r['strategy']:15s} | Сделок: {r['trades']:4d} | PnL: {r['total_pnl']:8.2f}$ | WR: {r['winrate']:5.1f}% | Сред: {r['avg_pnl']:8.4f}$")
else:
    print("   Нет данных!")

# 3. По парам
print("\n" + "=" * 60)
print("3. ПО ТОРГОВЫМ ПАРАМ")
print("=" * 60)

cursor.execute("""
    SELECT 
        symbol,
        COUNT(*) as trades,
        ROUND(SUM(pnl), 2) as total_pnl,
        ROUND(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as winrate
    FROM trades 
    WHERE status = 'CLOSED'
    GROUP BY symbol
    ORDER BY total_pnl DESC
""")
rows = cursor.fetchall()
if rows:
    for r in rows:
        emoji = "🟢" if (r['total_pnl'] or 0) > 0 else "🔴"
        print(f"   {emoji} {r['symbol']:12s} | Сделок: {r['trades']:4d} | PnL: {r['total_pnl']:8.2f}$ | WR: {r['winrate']:5.1f}%")
else:
    print("   Нет данных!")

# 4. Дневная динамика (последние 14 дней)
print("\n" + "=" * 60)
print("4. ДНЕВНАЯ ДИНАМИКА (последние 14 дней)")
print("=" * 60)

cursor.execute("""
    SELECT 
        date(exit_time) as day,
        COUNT(*) as trades,
        ROUND(SUM(pnl), 2) as daily_pnl
    FROM trades 
    WHERE status = 'CLOSED' AND exit_time IS NOT NULL
    GROUP BY day
    ORDER BY day DESC
    LIMIT 14
""")
rows = cursor.fetchall()
if rows:
    for r in reversed(rows):
        emoji = "🟢" if (r['daily_pnl'] or 0) > 0 else "🔴"
        print(f"   {emoji} {r['day']} | Сделок: {r['trades']:3d} | PnL: {r['daily_pnl']:8.2f}$")
else:
    print("   Нет данных!")

# 5. Серии убытков
print("\n" + "=" * 60)
print("5. АНАЛИЗ УБЫТКОВ")
print("=" * 60)

cursor.execute("""
    SELECT pnl, exit_time
    FROM trades 
    WHERE status = 'CLOSED'
    ORDER BY exit_time ASC
""")
rows = cursor.fetchall()

if rows:
    max_losses = 0
    current_losses = 0
    loss_streaks = []
    
    for r in rows:
        if (r['pnl'] or 0) < 0:
            current_losses += 1
        else:
            if current_losses > 0:
                loss_streaks.append(current_losses)
            max_losses = max(max_losses, current_losses)
            current_losses = 0
    
    if current_losses > 0:
        loss_streaks.append(current_losses)
        max_losses = max(max_losses, current_losses)
    
    print(f"   Максимальная серия убытков: {max_losses}")
    print(f"   Всего убыточных серий: {len(loss_streaks)}")
    
    if loss_streaks:
        avg_streak = sum(loss_streaks) / len(loss_streaks)
        print(f"   Средняя серия убытков: {avg_streak:.1f}")
else:
    print("   Нет данных!")

# 6. Ultra Scalping статистика
print("\n" + "=" * 60)
print("6. ULTRA SCALPING")
print("=" * 60)

cursor.execute("""
    SELECT 
        COUNT(*) as trades,
        ROUND(SUM(pnl), 4) as total_pnl,
        ROUND(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as winrate
    FROM trades 
    WHERE status = 'CLOSED' AND strategy = 'ultra_scalping'
""")
row = cursor.fetchone()
if row and row['trades']:
    print(f"   Сделок: {row['trades']}")
    print(f"   PnL: {row['total_pnl']}$")
    print(f"   Винрейт: {row['winrate']}%")
else:
    print("   Нет данных (сделки US не сохраняются в БД)")

# 7. Итоговая оценка
print("\n" + "=" * 60)
print("7. ИТОГОВАЯ ОЦЕНКА")
print("=" * 60)

cursor.execute("SELECT SUM(pnl) as total_pnl, COUNT(*) as total FROM trades WHERE status='CLOSED'")
row = cursor.fetchone()
total_pnl = row['total_pnl'] or 0
total_trades = row['total'] or 0

if total_trades == 0:
    print("   ❌ НЕТ ДАННЫХ — бот не совершил ни одной сделки!")
elif total_trades < 50:
    print(f"   🟡 МАЛО ДАННЫХ ({total_trades} сделок) — нужно минимум 100-200 для оценки")
elif total_pnl > 0 and total_trades >= 100:
    print(f"   🟢 Бот прибыльный! {total_pnl:+.2f}$ за {total_trades} сделок")
    print(f"   ✅ Можно пробовать реальную торговлю с МИНИМАЛЬНЫМ риском")
elif total_pnl <= 0 and total_trades >= 100:
    print(f"   🔴 Бот убыточный: {total_pnl:+.2f}$")
    print(f"   ❌ НЕ ГОТОВ к реальной торговле — нужно улучшать стратегии")
else:
    print(f"   🟡 Недостаточно данных для оценки")

print("=" * 60)

conn.close()
input("\nНажмите Enter для выхода...")