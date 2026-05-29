"""
Файл 14: webhook_server.py
Flask-сервер для приёма сигналов TradingView.
"""

from datetime import datetime

from flask import Flask, jsonify, request

from config import config
from database import get_db
from logger import logger


def create_app(bot_instance=None):
    app = Flask(__name__)

    @app.route("/webhook", methods=["POST"])
    def webhook():
        data = request.json or {}
        signal = {
            "type": data.get("action", "BUY").upper(),
            "symbol": data.get("ticker", ""),
            "price": float(data.get("price", 0)),
            "strategy": "tradingview",
            "timeframe": data.get("timeframe", ""),
            "confidence": 0.9,
            "reason": data.get("message", "TradingView signal"),
            "stop_loss": float(data.get("stop_loss", 0)),
            "take_profit": float(data.get("take_profit", 0)),
            "volume_ratio": 1.0,
            "rsi": 50,
        }

        logger.info(f"Webhook: {signal['symbol']} {signal['type']}")

        with get_db() as db:
            db.execute(
                """INSERT INTO signals (symbol, signal_type, strategy, timeframe,
                   price, rsi, volume_ratio, ml_confidence, reason)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    signal["symbol"],
                    signal["type"],
                    signal["strategy"],
                    signal["timeframe"],
                    signal["price"],
                    signal["rsi"],
                    signal["volume_ratio"],
                    signal["confidence"],
                    signal["reason"],
                ),
            )

        return jsonify({"status": "ok", "signal": signal})

    @app.route("/health")
    def health():
        return jsonify(
            {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "balance": bot_instance.balance if bot_instance else 0,
            }
        )

    @app.route("/stats")
    def stats():
        with get_db() as db:
            row = db.execute(
                "SELECT COUNT(*) total, SUM(pnl) pnl FROM trades WHERE status='CLOSED'"
            ).fetchone()
        return jsonify(
            {
                "total_trades": row["total"] or 0,
                "total_pnl": round(row["pnl"] or 0, 2),
                "balance": bot_instance.balance if bot_instance else 0,
            }
        )

    return app


def run_webhook(bot_instance=None):
    """Запустить вебхук-сервер."""
    app = create_app(bot_instance)
    logger.info(f"Webhook сервер: http://{config.WEBHOOK_HOST}:{config.WEBHOOK_PORT}")
    app.run(
        host=config.WEBHOOK_HOST,
        port=config.WEBHOOK_PORT,
        debug=False,
        use_reloader=False,
    )