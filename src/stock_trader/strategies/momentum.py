from __future__ import annotations

import pandas as pd

from stock_trader.models import Signal
from stock_trader.strategies.base import Strategy


class AbsoluteMomentumStrategy(Strategy):
    """Gary Antonacci-style absolute momentum: hold when N-month return is positive, else cash."""

    name = "absolute_momentum"

    def __init__(self, lookback: int = 252) -> None:
        if lookback < 20:
            raise ValueError("lookback must be at least 20")
        self.lookback = lookback

    def generate_signals(self, symbol: str, history: pd.DataFrame) -> list[Signal]:
        if "Close" not in history.columns:
            raise ValueError("history must include a Close column")

        frame = history.copy()
        frame["momentum"] = frame["Close"] / frame["Close"].shift(self.lookback) - 1
        frame["month"] = frame.index.to_period("M")
        monthly = frame.groupby("month").first()

        signals: list[Signal] = []
        in_market = False

        for period, row in monthly.iterrows():
            momentum = row["momentum"]
            if pd.isna(momentum):
                continue

            timestamp = row.name.to_timestamp() if hasattr(row.name, "to_timestamp") else pd.Timestamp(period).to_pydatetime()
            if isinstance(frame.index, pd.DatetimeIndex):
                month_rows = frame[frame.index.to_period("M") == period]
                if not month_rows.empty:
                    timestamp = month_rows.index[0].to_pydatetime()

            if momentum > 0 and not in_market:
                signals.append(
                    Signal(
                        symbol=symbol,
                        action="buy",
                        timestamp=timestamp,
                        reason=f"{self.lookback}-day return positive ({momentum * 100:.1f}%)",
                    )
                )
                in_market = True
            elif momentum <= 0 and in_market:
                signals.append(
                    Signal(
                        symbol=symbol,
                        action="sell",
                        timestamp=timestamp,
                        reason=f"{self.lookback}-day return non-positive ({momentum * 100:.1f}%)",
                    )
                )
                in_market = False

        return signals


class TrendFilterStrategy(Strategy):
    """Hold only when price is above the long-term moving average (trend filter)."""

    name = "trend_filter"

    def __init__(self, window: int = 200) -> None:
        if window < 20:
            raise ValueError("window must be at least 20")
        self.window = window

    def generate_signals(self, symbol: str, history: pd.DataFrame) -> list[Signal]:
        if "Close" not in history.columns:
            raise ValueError("history must include a Close column")

        frame = history.copy()
        frame["trend"] = frame["Close"].rolling(self.window).mean()
        frame = frame.dropna()

        signals: list[Signal] = []
        in_market = False
        previous_close = previous_trend = None

        for timestamp, row in frame.iterrows():
            close = float(row["Close"])
            trend = float(row["trend"])

            if previous_close is not None and previous_trend is not None:
                if not in_market and previous_close <= previous_trend and close > trend:
                    signals.append(
                        Signal(
                            symbol=symbol,
                            action="buy",
                            timestamp=timestamp.to_pydatetime(),
                            reason=f"Price crossed above {self.window}-day SMA",
                        )
                    )
                    in_market = True
                elif in_market and previous_close >= previous_trend and close < trend:
                    signals.append(
                        Signal(
                            symbol=symbol,
                            action="sell",
                            timestamp=timestamp.to_pydatetime(),
                            reason=f"Price crossed below {self.window}-day SMA",
                        )
                    )
                    in_market = False

            previous_close, previous_trend = close, trend

        return signals
