"""
Файл: indicators.py
Технические индикаторы (ИСПРАВЛЕНО).
"""

import numpy as np
import pandas as pd


class Indicators:
    """Набор технических индикаторов."""

    @staticmethod
    def rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def ema(series: pd.Series, period: int) -> pd.Series:
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def macd(
        series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> pd.DataFrame:
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        return pd.DataFrame(
            {
                "MACD": macd_line,
                "signal": signal_line,
                "histogram": macd_line - signal_line,
            }
        )

    @staticmethod
    def bollinger_bands(
        series: pd.Series, period: int = 20, std: float = 2.0
    ) -> pd.DataFrame:
        sma = series.rolling(period).mean()
        std_dev = series.rolling(period).std()
        return pd.DataFrame(
            {
                "middle": sma,
                "upper": sma + std * std_dev,
                "lower": sma - std * std_dev,
                "width": (sma + std * std_dev - (sma - std * std_dev)) / sma,
            }
        )

    @staticmethod
    def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        high_low = df["high"] - df["low"]
        high_close = abs(df["high"] - df["close"].shift())
        low_close = abs(df["low"] - df["close"].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.ewm(span=period, adjust=False).mean()

    @staticmethod
    def adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        high, low, close = df["high"], df["low"], df["close"]
        plus_dm = high.diff().clip(lower=0)
        minus_dm = (-low.diff()).clip(lower=0)
        tr = Indicators.atr(df, period) * period
        plus_di = 100 * (plus_dm.ewm(alpha=1 / period).mean() / tr.replace(0, np.nan))
        minus_di = 100 * (
            minus_dm.ewm(alpha=1 / period).mean() / tr.replace(0, np.nan)
        )
        dx = (
            100
            * abs(plus_di - minus_di)
            / (plus_di + minus_di).replace(0, np.nan)
        )
        adx_val = dx.ewm(alpha=1 / period).mean()
        return pd.DataFrame({"ADX": adx_val, "plus_DI": plus_di, "minus_DI": minus_di})

    @staticmethod
    def add_all(df: pd.DataFrame) -> pd.DataFrame:
        """Добавить все индикаторы к DataFrame."""
        if df.empty:
            return df

        # Проверка обязательных колонок
        required = ["open", "high", "low", "close", "volume"]
        if not all(c in df.columns for c in required):
            return df

        df = df.copy()
        close = df["close"]

        df["RSI"] = Indicators.rsi(close)
        df["EMA9"] = Indicators.ema(close, 9)
        df["EMA21"] = Indicators.ema(close, 21)
        df["EMA50"] = Indicators.ema(close, 50)
        df["EMA200"] = Indicators.ema(close, 200)

        macd = Indicators.macd(close)
        df["MACD"] = macd["MACD"]
        df["MACD_signal"] = macd["signal"]
        df["MACD_hist"] = macd["histogram"]

        bb = Indicators.bollinger_bands(close)
        df["BB_upper"] = bb["upper"]
        df["BB_middle"] = bb["middle"]
        df["BB_lower"] = bb["lower"]
        df["BB_width"] = bb["width"]

        df["ATR"] = Indicators.atr(df)
        df["ATR_pct"] = df["ATR"] / close * 100

        adx = Indicators.adx(df)
        df["ADX"] = adx["ADX"]
        df["plus_DI"] = adx["plus_DI"]
        df["minus_DI"] = adx["minus_DI"]

        df["volume_avg"] = df["volume"].rolling(20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_avg"]
        df["momentum"] = close.pct_change(10) * 100

        # Свечные паттерны
        df["body"] = df["close"] - df["open"]
        df["body_pct"] = abs(df["body"]) / df["open"] * 100
        df["upper_wick"] = df["high"] - df[["open", "close"]].max(axis=1)
        df["lower_wick"] = df[["open", "close"]].min(axis=1) - df["low"]

        return df