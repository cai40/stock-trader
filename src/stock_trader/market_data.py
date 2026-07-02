from __future__ import annotations

from datetime import datetime
from typing import Protocol

import pandas as pd

from stock_trader.models import Quote


class MarketDataProvider(Protocol):
    def get_quote(self, symbol: str) -> Quote:
        ...

    def get_history(
        self,
        symbol: str,
        start: str,
        end: str,
        interval: str = "1d",
    ) -> pd.DataFrame:
        ...


class YFinanceMarketData:
    def get_quote(self, symbol: str) -> Quote:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        price = float(info.last_price or info.previous_close)
        if price <= 0:
            raise ValueError(f"no price available for {symbol}")

        return Quote(symbol=symbol.upper(), price=price, timestamp=datetime.now())

    def get_history(
        self,
        symbol: str,
        start: str,
        end: str,
        interval: str = "1d",
    ) -> pd.DataFrame:
        import yfinance as yf

        frame = yf.download(
            symbol,
            start=start,
            end=end,
            interval=interval,
            progress=False,
            auto_adjust=True,
        )
        if frame.empty:
            raise ValueError(f"no historical data for {symbol} between {start} and {end}")

        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(0)

        frame = frame.rename(columns=str.title)
        frame.index = pd.to_datetime(frame.index)
        return frame
