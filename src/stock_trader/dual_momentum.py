from __future__ import annotations

import pandas as pd

from stock_trader.benchmarks import buy_and_hold_equity
from stock_trader.market_data import MarketDataProvider
from stock_trader.metrics import compute_max_drawdown
from stock_trader.models import BacktestResult


def dual_momentum_equity(
    risk_asset_history: pd.DataFrame,
    safe_asset_history: pd.DataFrame,
    initial_cash: float,
    lookback: int = 252,
) -> pd.Series:
    """GEM-style dual momentum: hold risk asset if its lookback return beats the safe asset."""
    risk = risk_asset_history.copy()
    safe = safe_asset_history.copy()
    risk.index = pd.to_datetime(risk.index)
    safe.index = pd.to_datetime(safe.index)

    combined_index = risk.index.intersection(safe.index)
    risk = risk.loc[combined_index]
    safe = safe.loc[combined_index]

    if risk.empty:
        return pd.Series(dtype=float)

    risk_ret = risk["Close"] / risk["Close"].shift(lookback) - 1
    safe_ret = safe["Close"] / safe["Close"].shift(lookback) - 1

    equities: list[float] = []
    holding_risk = True
    risk_shares = 0.0
    safe_shares = 0.0
    cash = initial_cash

    for i, (timestamp, row) in enumerate(risk.iterrows()):
        rr = risk_ret.iloc[i]
        sr = safe_ret.iloc[i]

        if i == 0:
            price = float(row["Close"])
            risk_shares = cash // price
            cash -= risk_shares * price
            holding_risk = True
        elif not pd.isna(rr) and not pd.isna(sr):
            want_risk = rr > sr
            if want_risk != holding_risk:
                if want_risk:
                    safe_price = float(safe.loc[timestamp, "Close"])
                    proceeds = safe_shares * safe_price
                    cash += proceeds
                    safe_shares = 0.0
                    risk_price = float(row["Close"])
                    risk_shares = cash // risk_price
                    cash -= risk_shares * risk_price
                else:
                    risk_price = float(row["Close"])
                    proceeds = risk_shares * risk_price
                    cash += proceeds
                    risk_shares = 0.0
                    safe_price = float(safe.loc[timestamp, "Close"])
                    safe_shares = cash // safe_price
                    cash -= safe_shares * safe_price
                holding_risk = want_risk

        risk_price = float(row["Close"])
        safe_price = float(safe.loc[timestamp, "Close"])
        equity = cash + risk_shares * risk_price + safe_shares * safe_price
        equities.append(equity)

    return pd.Series(equities, index=risk.index)


def run_dual_momentum(
    market_data: MarketDataProvider,
    risk_symbol: str,
    safe_symbol: str,
    start: str,
    end: str,
    initial_cash: float = 10_000.0,
    lookback: int = 252,
) -> BacktestResult:
    risk_history = market_data.get_history(risk_symbol, start=start, end=end)
    safe_history = market_data.get_history(safe_symbol, start=start, end=end)
    equity = dual_momentum_equity(risk_history, safe_history, initial_cash, lookback=lookback)
    buy_hold = buy_and_hold_equity(risk_history, initial_cash)

    end_equity = float(equity.iloc[-1]) if not equity.empty else initial_cash

    return BacktestResult(
        symbol=risk_symbol,
        strategy_name="dual_momentum",
        start_cash=initial_cash,
        end_equity=end_equity,
        max_drawdown=compute_max_drawdown(equity.tolist()),
        equity_curve=equity,
    )
