from __future__ import annotations

import pandas as pd


def align_histories(histories: dict[str, pd.DataFrame]) -> tuple[pd.DatetimeIndex, dict[str, pd.Series]]:
    """Align multiple OHLCV histories on a common trading-day index."""
    if not histories:
        return pd.DatetimeIndex([]), {}

    frames = {}
    for symbol, history in histories.items():
        frame = history.copy()
        frame.index = pd.to_datetime(frame.index)
        frames[symbol] = frame["Close"].astype(float)

    combined = pd.DataFrame(frames).dropna(how="any")
    if combined.empty:
        return pd.DatetimeIndex([]), {}

    prices = {symbol: combined[symbol] for symbol in combined.columns}
    return combined.index, prices


def returns_from_prices(prices: dict[str, pd.Series]) -> dict[str, pd.Series]:
    return {symbol: series.pct_change().fillna(0.0) for symbol, series in prices.items()}
