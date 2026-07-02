from __future__ import annotations

import pandas as pd

from stock_trader.models import Signal
from stock_trader.strategies.base import Strategy


class RSIStrategy(Strategy):
    name = "rsi"

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
    ) -> None:
        if period < 2:
            raise ValueError("period must be at least 2")
        if not 0 < oversold < overbought < 100:
            raise ValueError("oversold and overbought must satisfy 0 < oversold < overbought < 100")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signals(self, symbol: str, history: pd.DataFrame) -> list[Signal]:
        if "Close" not in history.columns:
            raise ValueError("history must include a Close column")

        frame = history.copy()
        delta = frame["Close"].diff()
        gain = delta.clip(lower=0).rolling(self.period).mean()
        loss = (-delta.clip(upper=0)).rolling(self.period).mean()
        rs = gain / loss.replace(0, float("nan"))
        frame["rsi"] = 100 - (100 / (1 + rs))
        frame = frame.dropna()

        signals: list[Signal] = []
        previous_rsi = None

        for timestamp, row in frame.iterrows():
            rsi = float(row["rsi"])

            if previous_rsi is not None:
                if previous_rsi >= self.oversold and rsi < self.oversold:
                    signals.append(
                        Signal(
                            symbol=symbol,
                            action="buy",
                            timestamp=timestamp.to_pydatetime(),
                            reason=f"RSI({self.period}) crossed below oversold ({self.oversold})",
                        )
                    )
                elif previous_rsi <= self.overbought and rsi > self.overbought:
                    signals.append(
                        Signal(
                            symbol=symbol,
                            action="sell",
                            timestamp=timestamp.to_pydatetime(),
                            reason=f"RSI({self.period}) crossed above overbought ({self.overbought})",
                        )
                    )

            previous_rsi = rsi

        return signals
