from __future__ import annotations

import time
from datetime import datetime, timedelta
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


def _normalize_index(index: pd.Index) -> pd.DatetimeIndex:
    """Return a timezone-naive DatetimeIndex (yfinance mixes tz-aware and naive)."""
    idx = pd.to_datetime(index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    return idx


def _normalize_history(frame: pd.DataFrame) -> pd.DataFrame:
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)

    frame = frame.rename(columns=str.title)
    frame.index = _normalize_index(frame.index)
    return frame.sort_index()


def _exclusive_end(end: str) -> str:
    """yfinance treats end date as exclusive; add one day so the last day is included."""
    return (pd.Timestamp(end) + timedelta(days=1)).strftime("%Y-%m-%d")


class YFinanceMarketData:
    def get_quote(self, symbol: str) -> Quote:
        import yfinance as yf

        ticker = yf.Ticker(symbol.upper())
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

        symbol = symbol.upper()
        end_exclusive = _exclusive_end(end)
        last_error: Exception | None = None

        for attempt in range(4):
            try:
                frame = yf.download(
                    symbol,
                    start=start,
                    end=end_exclusive,
                    interval=interval,
                    progress=False,
                    auto_adjust=True,
                    threads=False,
                )
                if not frame.empty:
                    return _normalize_history(frame)
            except Exception as exc:
                last_error = exc

            try:
                frame = yf.Ticker(symbol).history(
                    start=start,
                    end=end_exclusive,
                    interval=interval,
                    auto_adjust=True,
                )
                if not frame.empty:
                    return _normalize_history(frame)
            except Exception as exc:
                last_error = exc

            if attempt < 3:
                time.sleep(1.5 * (attempt + 1))

        detail = f" ({last_error})" if last_error else ""
        raise ValueError(
            f"no historical data for {symbol} between {start} and {end}{detail}. "
            "Try again in a minute, pick SPY or AAPL, or use a shorter date range."
        )
