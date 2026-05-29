import sqlite3
conn = sqlite3.connect('trading_bot.db')
conn.execute("UPDATE trades SET status='CLOSED', exit_reason='reset' WHERE status='OPEN'")
conn.commit()
conn.close()
print('Позиции сброшены')