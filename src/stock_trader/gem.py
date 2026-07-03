from __future__ import annotations

import pandas as pd

from stock_trader.multi_asset import align_histories, returns_from_prices

LOOKBACK = 252


def _pick_gem_asset(
    spy_close: pd.Series,
    efa_close: pd.Series,
    shy_close: pd.Series,
    at_index: int,
) -> str:
    if at_index < LOOKBACK:
        return "SPY"

    spy_ret = float(spy_close.iloc[at_index] / spy_close.iloc[at_index - LOOKBACK] - 1)
    shy_ret = float(shy_close.iloc[at_index] / shy_close.iloc[at_index - LOOKBACK] - 1)

    if spy_ret <= shy_ret:
        return "SHY"

    efa_ret = float(efa_close.iloc[at_index] / efa_close.iloc[at_index - LOOKBACK] - 1)
    return "SPY" if spy_ret >= efa_ret else "EFA"


def gem_dual_momentum_equity(
    spy_history: pd.DataFrame,
    efa_history: pd.DataFrame,
    shy_history: pd.DataFrame,
    initial_cash: float,
) -> pd.Series:
    """Antonacci GEM: absolute + relative momentum across SPY, EFA, and SHY."""
    index, prices = align_histories({"SPY": spy_history, "EFA": efa_history, "SHY": shy_history})
    if index.empty:
        return pd.Series(dtype=float)

    returns = returns_from_prices(prices)
    equity = initial_cash
    equities: list[float] = []
    holding = "SPY"
    last_month = None

    for i, timestamp in enumerate(index):
        month = timestamp.to_period("M")
        if last_month is None or month != last_month:
            holding = _pick_gem_asset(prices["SPY"], prices["EFA"], prices["SHY"], i)
            last_month = month

        equity *= 1.0 + float(returns[holding].iloc[i])
        equities.append(equity)

    return pd.Series(equities, index=index)
