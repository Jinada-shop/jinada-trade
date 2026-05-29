"""
Файл: api_server.py
REST API для внешних подключений + Grafana метрики.
"""

import json
from datetime import datetime
from io import BytesIO

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

from config import config
from database import get_db
from logger import logger
from pnl_chart import PnLChart

app = Flask(__name__)
CORS(app)


@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})


@app.route('/api/balance')
def balance():
    with get_db() as db:
        pnl = db.execute("SELECT SUM(pnl) FROM trades WHERE status='CLOSED'").fetchone()[0] or 0
        open_pos = db.execute("SELECT COUNT(*) FROM trades WHERE status='OPEN'").fetchone()[0]
    return jsonify({
        'balance': round(config.INITIAL_BALANCE + pnl, 2),
        'pnl': round(pnl, 2),
        'open_positions': open_pos,
    })


@app.route('/api/signals')
def signals():
    limit = request.args.get('limit', 50, type=int)
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM signals ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route('/api/trades')
def trades():
    limit = request.args.get('limit', 50, type=int)
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM trades WHERE status='CLOSED' ORDER BY exit_time DESC LIMIT ?", (limit,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route('/api/stats')
def stats():
    with get_db() as db:
        total = db.execute("SELECT COUNT(*) FROM trades WHERE status='CLOSED'").fetchone()[0]
        wins = db.execute("SELECT COUNT(*) FROM trades WHERE status='CLOSED' AND pnl>0").fetchone()[0]
        pnl = db.execute("SELECT SUM(pnl) FROM trades WHERE status='CLOSED'").fetchone()[0] or 0
        today = db.execute(
            "SELECT COUNT(*), SUM(pnl) FROM trades WHERE status='CLOSED' AND date(exit_time)=date('now')"
        ).fetchone()
        best = db.execute("SELECT symbol, MAX(pnl) FROM trades WHERE status='CLOSED'").fetchone()
        worst = db.execute("SELECT symbol, MIN(pnl) FROM trades WHERE status='CLOSED'").fetchone()

    win_rate = (wins / total * 100) if total > 0 else 0
    return jsonify({
        'total_trades': total,
        'win_rate': round(win_rate, 1),
        'total_pnl': round(pnl, 2),
        'today_trades': today[0] or 0,
        'today_pnl': round(today[1] or 0, 2),
        'best_trade': {'symbol': best[0], 'pnl': round(best[1], 2)} if best and best[0] else None,
        'worst_trade': {'symbol': worst[0], 'pnl': round(worst[1], 2)} if worst and worst[0] else None,
        'balance': round(config.INITIAL_BALANCE + pnl, 2),
    })


@app.route('/api/chart/pnl')
def chart_pnl():
    buf = PnLChart.generate()
    if buf:
        return send_file(buf, mimetype='image/png')
    return jsonify({'error': 'No data'}), 404


@app.route('/api/compare')
def compare_market():
    """Сравнение с рынком."""
    import requests
    try:
        resp = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=5)
        btc_price = float(resp.json()['price'])
    except Exception:
        btc_price = 0

    with get_db() as db:
        pnl = db.execute("SELECT SUM(pnl) FROM trades WHERE status='CLOSED'").fetchone()[0] or 0

    bot_return = (pnl / config.INITIAL_BALANCE * 100) if config.INITIAL_BALANCE > 0 else 0

    return jsonify({
        'bot_return_pct': round(bot_return, 2),
        'bot_pnl': round(pnl, 2),
        'btc_price': btc_price,
        'message': f"Бот: {bot_return:+.1f}%" + (f" | BTC: {btc_price}" if btc_price else ""),
    })


@app.route('/api/webhook/tradingview', methods=['POST'])
def tradingview_webhook():
    """Приём сигналов от TradingView."""
    data = request.json or {}
    logger.info(f"📡 TradingView сигнал: {data.get('ticker', 'unknown')} {data.get('action', 'unknown')}")

    with get_db() as db:
        db.execute(
            "INSERT INTO signals (symbol,signal_type,strategy,timeframe,price,rsi,volume_ratio,ml_confidence) VALUES (?,?,?,?,?,?,?,?)",
            (data.get('ticker', ''), data.get('action', 'BUY').upper(), 'tradingview',
             data.get('timeframe', '1h'), data.get('price', 0), 50, 1, 0.9),
        )

    return jsonify({'status': 'received', 'signal': data})


def run_api_server():
    logger.info(f"🌐 REST API: http://0.0.0.0:{config.API_PORT}")
    app.run(host='0.0.0.0', port=config.API_PORT, debug=False, use_reloader=False)