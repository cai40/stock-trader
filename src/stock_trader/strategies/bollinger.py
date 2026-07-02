from __future__ import annotations

import pandas as pd

from stock_trader.models import Signal
from stock_trader.strategies.base import Strategy


class BollingerBandsStrategy(Strategy):
    name = "bollinger"

    def __init__(self, window: int = 20, num_std: float = 2.0) -> None:
        if window < 2:
            raise ValueError("window must be at least 2")
        self.window = window
        self.num_std = num_std

    def generate_signals(self, symbol: str, history: pd.DataFrame) -> list[Signal]:
        if "Close" not in history.columns:
            raise ValueError("history must include a Close column")

        frame = history.copy()
        frame["mid"] = frame["Close"].rolling(self.window).mean()
        frame["std"] = frame["Close"].rolling(self.window).std()
        frame["lower"] = frame["mid"] - self.num_std * frame["std"]
        frame["upper"] = frame["mid"] + self.num_std * frame["std"]
        frame = frame.dropna()

        signals: list[Signal] = []
        previous_close = previous_lower = previous_upper = None

        for timestamp, row in frame.iterrows():
            close = float(row["Close"])
            lower = float(row["lower"])
            upper = float(row["upper"])

            if previous_close is not None and previous_lower is not None and previous_upper is not None:
                if previous_close >= previous_lower and close < lower:
                    signals.append(
                        Signal(
                            symbol=symbol,
                            action="buy",
                            timestamp=timestamp.to_pydatetime(),
                            reason="Price crossed below lower Bollinger band",
                        )
                    )
                elif previous_close <= previous_upper and close > upper:
                    signals.append(
                        Signal(
                            symbol=symbol,
                            action="sell",
                            timestamp=timestamp.to_pydatetime(),
                            reason="Price crossed above upper Bollinger band",
                        )
                    )

            previous_close, previous_lower, previous_upper = close, lower, upper

        return signals
