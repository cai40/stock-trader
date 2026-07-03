from __future__ import annotations

import pandas as pd

from stock_trader.multi_asset import align_histories, returns_from_prices

VOL_WINDOW = 20
ASSETS = ("SPY", "TLT", "GLD", "SHY")


def risk_parity_equity(
    histories: dict[str, pd.DataFrame],
    initial_cash: float,
) -> pd.Series:
    """Inverse-volatility weights across SPY, TLT, GLD, and SHY, rebalanced monthly."""
    index, prices = align_histories(histories)
    if index.empty:
        return pd.Series(dtype=float)

    returns = returns_from_prices(prices)
    equity = initial_cash
    equities: list[float] = []
    weights = {symbol: 1.0 / len(prices) for symbol in prices}
    last_month = None

    for i, timestamp in enumerate(index):
        month = timestamp.to_period("M")
        if last_month is None or month != last_month:
            inv_vols: dict[str, float] = {}
            for symbol, series in prices.items():
                vol = returns[symbol].iloc[max(0, i - VOL_WINDOW + 1) : i + 1].std()
                inv_vols[symbol] = 1.0 / vol if vol and vol > 0 else 1.0
            total = sum(inv_vols.values())
            weights = {symbol: inv / total for symbol, inv in inv_vols.items()}
            last_month = month

        day_return = sum(weights[symbol] * float(returns[symbol].iloc[i]) for symbol in prices)
        equity *= 1.0 + day_return
        equities.append(equity)

    return pd.Series(equities, index=index)
