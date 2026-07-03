from __future__ import annotations

import pandas as pd


def vol_target_equity(
    history: pd.DataFrame,
    initial_cash: float,
    target_vol: float = 0.15,
    vol_window: int = 20,
    max_leverage: float = 1.5,
) -> pd.Series:
    """Scale SPY exposure inversely to realized volatility.

    In calm markets exposure rises above 100% (up to max_leverage), which can
    outperform buy-and-hold on long bull runs while cutting size before crashes.
    """
    if "Close" not in history.columns:
        raise ValueError("history must include a Close column")
    if history.empty:
        return pd.Series(dtype=float)

    prices = history["Close"].astype(float)
    daily_returns = prices.pct_change().fillna(0.0)
    realized_vol = daily_returns.rolling(vol_window).std() * (252**0.5)
    weight = (target_vol / realized_vol).clip(0.0, max_leverage).shift(1).fillna(1.0)

    equities: list[float] = [initial_cash]
    for i in range(1, len(history)):
        exposure = float(weight.iloc[i])
        day_return = float(daily_returns.iloc[i])
        equities.append(equities[-1] * (1.0 + exposure * day_return))

    return pd.Series(equities, index=history.index)
