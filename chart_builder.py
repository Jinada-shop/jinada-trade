"""
Файл: chart_builder.py
Графики без warning.
"""

from io import BytesIO
from typing import Dict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
import warnings
warnings.filterwarnings('ignore')


class ChartBuilder:
    """График с сигналом."""

    @staticmethod
    def build(df: pd.DataFrame, signal: Dict) -> BytesIO:
        df_plot = df.tail(100)[["open", "high", "low", "close", "volume"]].copy()

        add_plots = []
        if "EMA9" in df.columns:
            add_plots.append(mpf.make_addplot(df["EMA9"].tail(100), color="blue", width=1))
        if "EMA21" in df.columns:
            add_plots.append(mpf.make_addplot(df["EMA21"].tail(100), color="orange", width=1))
        if "BB_upper" in df.columns:
            add_plots.append(mpf.make_addplot(df["BB_upper"].tail(100), color="gray", linestyle="--", width=0.5))
            add_plots.append(mpf.make_addplot(df["BB_lower"].tail(100), color="gray", linestyle="--", width=0.5))

        mc = mpf.make_marketcolors(up="green", down="red", volume={"up": "green", "down": "red"})
        style = mpf.make_mpf_style(marketcolors=mc, gridstyle="--")

        kwargs = dict(
            type="candle", style=style, volume=True,
            title=f"{signal['symbol']} - {signal['type']}",
            returnfig=True, figsize=(12, 8),
        )
        if add_plots:
            kwargs["addplot"] = add_plots

        fig, axes = mpf.plot(df_plot, **kwargs)

        ax = axes[0]
        color = "green" if signal["type"] == "BUY" else "red"
        ax.axhline(y=signal["price"], color=color, linewidth=2, alpha=0.7)

        if signal.get("stop_loss"):
            ax.axhline(y=signal["stop_loss"], color="red", linestyle="--", alpha=0.3)
        if signal.get("take_profit"):
            ax.axhline(y=signal["take_profit"], color="green", linestyle="--", alpha=0.3)

        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        buf.seek(0)
        plt.close(fig)
        return buf