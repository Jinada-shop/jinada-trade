"""
Файл 9: anomaly_detector.py
Детектор рыночных аномалий (Isolation Forest).
"""

from typing import Dict

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


class AnomalyDetector:
    """Поиск пампов / дампов / аномалий."""

    def __init__(self):
        self.model = IsolationForest(contamination=0.05, random_state=42)
        self.scaler = StandardScaler()

    # ------------------------------------------------------------------
    def detect(self, df: pd.DataFrame) -> Dict:
        """Проверить последнюю свечу на аномальность."""
        if len(df) < 20:
            return {"anomaly": False}

        features = pd.DataFrame(
            {
                "price_change_5": df["close"].pct_change(5).fillna(0) * 100,
                "volume_ratio": (
                    df["volume"] / df["volume"].rolling(20).mean()
                ).fillna(1),
                "candle_size": abs(df["close"] - df["open"]) / df["open"] * 100,
                "wick_ratio": (df["high"] - df["low"])
                / (abs(df["close"] - df["open"]) + 1e-8),
                "volatility": df["close"]
                .pct_change()
                .rolling(10)
                .std()
                .fillna(0),
            }
        )

        X = self.scaler.fit_transform(features.fillna(0))
        preds = self.model.fit_predict(X)
        scores = self.model.score_samples(X)

        if preds[-1] == -1:
            severity = (
                abs(scores[-1]) / max(abs(scores)) if max(abs(scores)) > 0 else 0
            )
            pc = features["price_change_5"].iloc[-1]
            vol = features["volume_ratio"].iloc[-1]

            if pc > 5 and vol > 3:
                anom_type = "PUMP"
            elif pc < -5 and vol > 3:
                anom_type = "DUMP"
            elif abs(pc) > 10:
                anom_type = "FLASH_CRASH"
            else:
                anom_type = "UNUSUAL"

            return {
                "anomaly": True,
                "type": anom_type,
                "severity": float(severity),
                "should_pause": severity > 0.7,
            }

        return {"anomaly": False}