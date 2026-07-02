from __future__ import annotations

import pandas as pd

from stock_trader.models import Signal
from stock_trader.strategies.base import Strategy


class MACDStrategy(Strategy):
    name = "macd"

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> None:
        if fast_period >= slow_period:
            raise ValueError("fast_period must be smaller than slow_period")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def generate_signals(self, symbol: str, history: pd.DataFrame) -> list[Signal]:
        if "Close" not in history.columns:
            raise ValueError("history must include a Close column")

        frame = history.copy()
        fast = frame["Close"].ewm(span=self.fast_period, adjust=False).mean()
        slow = frame["Close"].ewm(span=self.slow_period, adjust=False).mean()
        frame["macd"] = fast - slow
        frame["signal"] = frame["macd"].ewm(span=self.signal_period, adjust=False).mean()
        frame = frame.dropna()

        signals: list[Signal] = []
        previous_macd = previous_signal = None

        for timestamp, row in frame.iterrows():
            macd = float(row["macd"])
            signal_line = float(row["signal"])

            if previous_macd is not None and previous_signal is not None:
                if previous_macd <= previous_signal and macd > signal_line:
                    signals.append(
                        Signal(
                            symbol=symbol,
                            action="buy",
                            timestamp=timestamp.to_pydatetime(),
                            reason="MACD crossed above signal line",
                        )
                    )
                elif previous_macd >= previous_signal and macd < signal_line:
                    signals.append(
                        Signal(
                            symbol=symbol,
                            action="sell",
                            timestamp=timestamp.to_pydatetime(),
                            reason="MACD crossed below signal line",
                        )
                    )

            previous_macd, previous_signal = macd, signal_line

        return signals
