from __future__ import annotations

import pandas as pd

SMA_MONTHS = 10


def faber_sma10_equity(history: pd.DataFrame, initial_cash: float) -> pd.Series:
    """Meb Faber tactical rule: hold when price is above the 10-month SMA, else cash."""
    if history.empty or "Close" not in history.columns:
        return pd.Series(dtype=float)

    daily = history.copy()
    daily.index = pd.to_datetime(daily.index)
    close = daily["Close"].astype(float)
    daily_returns = close.pct_change().fillna(0.0)

    monthly = close.resample("ME").last()
    monthly_sma = monthly.rolling(SMA_MONTHS).mean()
    in_market = (monthly > monthly_sma).reindex(close.index, method="ffill").fillna(False)

    equity = initial_cash
    equities: list[float] = []
    for i in range(len(close)):
        day_return = float(daily_returns.iloc[i]) if bool(in_market.iloc[i]) else 0.0
        equity *= 1.0 + day_return
        equities.append(equity)

    return pd.Series(equities, index=close.index)
