from __future__ import annotations

from enum import Enum

import pandas as pd

LOOKBACK_RETURN = 252
LOOKBACK_VOL = 20
LOOKBACK_TREND = 200
LOOKBACK_DRAWDOWN = 252

CRISIS_RETURN_THRESHOLD = -0.03
CRISIS_DRAWDOWN_THRESHOLD = -0.10
BULL_RETURN_THRESHOLD = 0.05
BULL_VOL_FLOOR = 0.13
LOW_VOL_CEILING = 0.13


class MarketRegime(str, Enum):
    """Market environment used to pick the best-suited strategy."""

    BULL = "bull"
    CRISIS = "crisis"
    CHOPPY = "choppy"
    LOW_VOL_GRIND = "low_vol_grind"


REGIME_LABELS: dict[MarketRegime, str] = {
    MarketRegime.BULL: "Bull market",
    MarketRegime.CRISIS: "Crisis / recovery",
    MarketRegime.CHOPPY: "Choppy / sideways",
    MarketRegime.LOW_VOL_GRIND: "Low-vol grind higher",
}

REGIME_STRATEGY: dict[MarketRegime, str] = {
    MarketRegime.BULL: "buy_and_hold",
    MarketRegime.CRISIS: "dual_momentum",
    MarketRegime.CHOPPY: "bollinger",
    MarketRegime.LOW_VOL_GRIND: "vol_target",
}


def regime_label(regime: MarketRegime) -> str:
    return REGIME_LABELS[regime]


def _annualized_vol(returns: pd.Series, window: int) -> float:
    vol = returns.rolling(window).std().iloc[-1]
    if pd.isna(vol):
        return float("nan")
    return float(vol * (252**0.5))


def detect_regime(history: pd.DataFrame) -> MarketRegime:
    """Classify the market at the last row of *history* using only past data.

    Rules (first match wins):

    1. **Crisis** — 12-month return below -3%, or drawdown from the 1-year
       high worse than -10% (crash / slow recovery).
    2. **Low-vol grind** — positive 12-month return, annualized vol below 13%,
       and price above the 200-day SMA (calm rally).
    3. **Bull** — 12-month return above 5%, price above 200 SMA, vol at least
       13% (strong trending rally).
    4. **Choppy** — everything else (sideways, below trend, mixed signals).
    """
    if "Close" not in history.columns or len(history) < LOOKBACK_TREND:
        return MarketRegime.CHOPPY

    close = history["Close"].astype(float)
    price = float(close.iloc[-1])
    daily_returns = close.pct_change()

    ret_12m = (
        float(price / close.iloc[-LOOKBACK_RETURN] - 1)
        if len(close) > LOOKBACK_RETURN
        else 0.0
    )
    vol = _annualized_vol(daily_returns, LOOKBACK_VOL)
    sma200 = float(close.rolling(LOOKBACK_TREND).mean().iloc[-1])
    peak = float(close.rolling(LOOKBACK_DRAWDOWN).max().iloc[-1])
    drawdown = price / peak - 1 if peak > 0 else 0.0

    if ret_12m < CRISIS_RETURN_THRESHOLD or drawdown <= CRISIS_DRAWDOWN_THRESHOLD:
        return MarketRegime.CRISIS

    above_trend = price > sma200

    if ret_12m > 0 and not pd.isna(vol) and vol < LOW_VOL_CEILING and above_trend:
        return MarketRegime.LOW_VOL_GRIND

    if (
        ret_12m > BULL_RETURN_THRESHOLD
        and above_trend
        and not pd.isna(vol)
        and vol >= BULL_VOL_FLOOR
    ):
        return MarketRegime.BULL

    return MarketRegime.CHOPPY


def detect_regime_series(history: pd.DataFrame) -> pd.Series:
    """Return a regime label for each row (expanding window, monthly updates)."""
    regimes: list[MarketRegime] = []
    current = MarketRegime.CHOPPY
    last_month: pd.Period | None = None

    for i in range(len(history)):
        ts = history.index[i]
        month = ts.to_period("M")
        if last_month is None or month != last_month:
            current = detect_regime(history.iloc[: i + 1])
            last_month = month
        regimes.append(current)

    return pd.Series(regimes, index=history.index)
