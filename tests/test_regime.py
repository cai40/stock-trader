from __future__ import annotations

import pandas as pd
import pytest

from stock_trader.regime import MarketRegime, detect_regime


def _history_from_prices(prices: list[float], start: str = "2010-01-01") -> pd.DataFrame:
    dates = pd.date_range(start, periods=len(prices), freq="B")
    return pd.DataFrame({"Close": prices}, index=dates)


def test_detect_regime_defaults_to_choppy_with_short_history() -> None:
    history = _history_from_prices([100.0] * 50)
    assert detect_regime(history) == MarketRegime.CHOPPY


def test_detect_regime_identifies_crisis_on_deep_drawdown() -> None:
    prices = [200.0] * 260 + [170.0] * 20
    history = _history_from_prices(prices)
    assert detect_regime(history) == MarketRegime.CRISIS


def test_detect_regime_identifies_bull_on_strong_uptrend() -> None:
    prices = [100 + i * 0.4 for i in range(320)]
    history = _history_from_prices(prices)
    regime = detect_regime(history)
    assert regime in {MarketRegime.BULL, MarketRegime.LOW_VOL_GRIND}


def test_detect_regime_identifies_low_vol_grind() -> None:
    prices = [100 + i * 0.05 for i in range(320)]
    history = _history_from_prices(prices)
    assert detect_regime(history) == MarketRegime.LOW_VOL_GRIND
