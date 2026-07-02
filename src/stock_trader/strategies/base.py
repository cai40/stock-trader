from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from stock_trader.models import Signal


class Strategy(ABC):
    name: str

    @abstractmethod
    def generate_signals(self, symbol: str, history: pd.DataFrame) -> list[Signal]:
        ...
