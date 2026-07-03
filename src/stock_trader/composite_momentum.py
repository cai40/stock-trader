from __future__ import annotations

import pandas as pd

LOOKBACK_LONG = 252
LOOKBACK_SHORT = 126


def composite_momentum_equity(
    risk_history: pd.DataFrame,
    safe_history: pd.DataFrame,
    initial_cash: float,
) -> pd.Series:
    """Blend 6- and 12-month momentum; hold risk asset when composite score is positive."""
    risk = risk_history.copy()
    safe = safe_history.copy()
    risk.index = pd.to_datetime(risk.index)
    safe.index = pd.to_datetime(safe.index)
    idx = risk.index.intersection(safe.index)
    risk = risk.loc[idx]
    safe = safe.loc[idx]

    if risk.empty:
        return pd.Series(dtype=float)

    risk_close = risk["Close"].astype(float)
    safe_close = safe["Close"].astype(float)
    risk_returns = risk_close.pct_change().fillna(0.0)
    safe_returns = safe_close.pct_change().fillna(0.0)

    equity = initial_cash
    equities: list[float] = []
    holding_risk = True
    last_month = None

    for i, timestamp in enumerate(idx):
        month = timestamp.to_period("M")
        if last_month is None or month != last_month:
            if i >= LOOKBACK_LONG:
                ret_12m = float(risk_close.iloc[i] / risk_close.iloc[i - LOOKBACK_LONG] - 1)
                ret_6m = float(risk_close.iloc[i] / risk_close.iloc[i - LOOKBACK_SHORT] - 1)
                score = 0.5 * ret_6m + 0.5 * ret_12m
                holding_risk = score > 0
            last_month = month

        if holding_risk:
            equity *= 1.0 + float(risk_returns.iloc[i])
        else:
            equity *= 1.0 + float(safe_returns.iloc[i])

        equities.append(equity)

    return pd.Series(equities, index=idx)
