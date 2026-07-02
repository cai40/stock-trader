from __future__ import annotations

import pandas as pd

from stock_trader.models import Signal
from stock_trader.strategies.base import Strategy


class EMACrossoverStrategy(Strategy):
    name = "ema_crossover"

    def __init__(self, fast_window: int = 12, slow_window: int = 26) -> None:
        if fast_window >= slow_window:
            raise ValueError("fast_window must be smaller than slow_window")
        self.fast_window = fast_window
        self.slow_window = slow_window

    def generate_signals(self, symbol: str, history: pd.DataFrame) -> list[Signal]:
        if "Close" not in history.columns:
            raise ValueError("history must include a Close column")

        frame = history.copy()
        frame["fast_ema"] = frame["Close"].ewm(span=self.fast_window, adjust=False).mean()
        frame["slow_ema"] = frame["Close"].ewm(span=self.slow_window, adjust=False).mean()
        frame = frame.dropna()

        signals: list[Signal] = []
        previous_fast = previous_slow = None

        for timestamp, row in frame.iterrows():
            fast = float(row["fast_ema"])
            slow = float(row["slow_ema"])

            if previous_fast is not None and previous_slow is not None:
                if previous_fast <= previous_slow and fast > slow:
                    signals.append(
                        Signal(
                            symbol=symbol,
                            action="buy",
                            timestamp=timestamp.to_pydatetime(),
                            reason=f"{self.fast_window}-day EMA crossed above {self.slow_window}-day EMA",
                        )
                    )
                elif previous_fast >= previous_slow and fast < slow:
                    signals.append(
                        Signal(
                            symbol=symbol,
                            action="sell",
                            timestamp=timestamp.to_pydatetime(),
                            reason=f"{self.fast_window}-day EMA crossed below {self.slow_window}-day EMA",
                        )
                    )

            previous_fast, previous_slow = fast, slow

        return signals
