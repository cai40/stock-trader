from __future__ import annotations

import pandas as pd

from stock_trader.regime import REGIME_STRATEGY, MarketRegime, detect_regime
from stock_trader.strategies.bollinger import BollingerBandsStrategy

DUAL_LOOKBACK = 252


def _vol_weights(history: pd.DataFrame) -> pd.Series:
    """Daily vol-target weights aligned with vol_target_equity."""
    prices = history["Close"].astype(float)
    daily_returns = prices.pct_change().fillna(0.0)
    realized_vol = daily_returns.rolling(20).std() * (252**0.5)
    return (0.15 / realized_vol).clip(0.0, 1.5).shift(1).fillna(1.0)


def _bollinger_signal_lookup(history: pd.DataFrame, symbol: str) -> dict:
    signals = BollingerBandsStrategy().generate_signals(symbol, history)
    return {signal.timestamp: signal.action for signal in signals}


def hybrid_regime_equity(
    risk_history: pd.DataFrame,
    safe_history: pd.DataFrame,
    initial_cash: float,
    *,
    symbol: str = "SPY",
) -> pd.Series:
    """Switch between sub-strategies when the detected market regime changes.

    Regime is re-evaluated on the first trading day of each month. When it
    changes, the portfolio is reset to cash and the new regime's strategy
    takes over.
    """
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
    risk_mom = risk_close / risk_close.shift(DUAL_LOOKBACK) - 1
    safe_mom = safe_close / safe_close.shift(DUAL_LOOKBACK) - 1
    vol_weights = _vol_weights(risk)
    bollinger_signals = _bollinger_signal_lookup(risk, symbol)

    equity = initial_cash
    equities: list[float] = []
    regime: MarketRegime | None = None
    last_month: pd.Period | None = None

    in_risk_market = False
    dual_holds_risk = True

    for i, (timestamp, _) in enumerate(risk.iterrows()):
        hist = risk.iloc[: i + 1]
        month = timestamp.to_period("M")
        if last_month is None or month != last_month:
            new_regime = detect_regime(hist)
            if new_regime != regime:
                regime = new_regime
                in_risk_market = False
                dual_holds_risk = True
            last_month = month

        assert regime is not None
        active = REGIME_STRATEGY[regime]
        dt = timestamp.to_pydatetime()
        day_risk_ret = float(risk_returns.iloc[i])
        day_safe_ret = float(safe_returns.iloc[i])

        if active == "buy_and_hold":
            equity *= 1.0 + day_risk_ret

        elif active == "vol_target":
            weight = float(vol_weights.iloc[i])
            equity *= 1.0 + weight * day_risk_ret

        elif active == "dual_momentum":
            rr = risk_mom.iloc[i]
            sr = safe_mom.iloc[i]
            if not pd.isna(rr) and not pd.isna(sr):
                want_risk = bool(rr > sr)
                if want_risk != dual_holds_risk:
                    dual_holds_risk = want_risk
            if dual_holds_risk:
                equity *= 1.0 + day_risk_ret
            else:
                equity *= 1.0 + day_safe_ret

        elif active == "bollinger":
            action = bollinger_signals.get(dt)
            if action == "buy":
                in_risk_market = True
            elif action == "sell":
                in_risk_market = False
            if in_risk_market:
                equity *= 1.0 + day_risk_ret

        equities.append(equity)

    return pd.Series(equities, index=risk.index)
