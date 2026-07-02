from __future__ import annotations

import pandas as pd

from stock_trader.metrics import compute_max_drawdown


def buy_and_hold_equity(history: pd.DataFrame, initial_cash: float) -> pd.Series:
    if history.empty:
        return pd.Series(dtype=float)

    first_price = float(history.iloc[0]["Close"])
    if first_price <= 0:
        return pd.Series([initial_cash] * len(history), index=history.index)

    shares = initial_cash // first_price
    cash = initial_cash - shares * first_price
    values = [cash + shares * float(row["Close"]) for _, row in history.iterrows()]
    return pd.Series(values, index=history.index)


def equity_metrics(equity: pd.Series, initial_cash: float) -> tuple[float, float]:
    if equity.empty:
        return initial_cash, 0.0
    end_equity = float(equity.iloc[-1])
    max_drawdown = compute_max_drawdown(equity.tolist())
    return end_equity, max_drawdown
