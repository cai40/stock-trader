from __future__ import annotations

import pandas as pd

from stock_trader.faber import faber_sma10_equity
from stock_trader.gem import gem_dual_momentum_equity
from stock_trader.metrics import compute_sharpe_ratio
from stock_trader.regime import MarketRegime, detect_regime
from stock_trader.risk_parity import risk_parity_equity


def _history(prices: list[float], start: str = "2010-01-01") -> pd.DataFrame:
    dates = pd.date_range(start, periods=len(prices), freq="B")
    return pd.DataFrame({"Close": prices}, index=dates)


def test_detect_regime_crisis_on_drawdown() -> None:
    prices = [200.0] * 260 + [170.0] * 20
    assert detect_regime(_history(prices)) == MarketRegime.CRISIS


def test_faber_sma10_equity_curve() -> None:
    prices = [100 + i * 0.2 for i in range(300)]
    equity = faber_sma10_equity(_history(prices), 10_000.0)
    assert len(equity) == 300
    assert float(equity.iloc[-1]) > 0


def test_gem_dual_momentum_equity_curve() -> None:
    dates = pd.date_range("2015-01-01", periods=400, freq="B")
    spy = pd.DataFrame({"Close": [100 + i * 0.15 for i in range(400)]}, index=dates)
    efa = pd.DataFrame({"Close": [80 + i * 0.1 for i in range(400)]}, index=dates)
    shy = pd.DataFrame({"Close": [50 + i * 0.01 for i in range(400)]}, index=dates)
    equity = gem_dual_momentum_equity(spy, efa, shy, 10_000.0)
    assert len(equity) == 400
    assert float(equity.iloc[-1]) > 0


def test_risk_parity_equity_curve() -> None:
    dates = pd.date_range("2015-01-01", periods=200, freq="B")
    histories = {
        symbol: pd.DataFrame({"Close": [100 + i * 0.05 for i in range(200)]}, index=dates)
        for symbol in ("SPY", "TLT", "GLD", "SHY")
    }
    equity = risk_parity_equity(histories, 10_000.0)
    assert len(equity) == 200
    assert float(equity.iloc[-1]) > 0


def test_compute_sharpe_ratio_positive_on_uptrend() -> None:
    dates = pd.date_range("2020-01-01", periods=252, freq="B")
    equity = pd.Series([10_000 * (1.001**i) for i in range(252)], index=dates)
    assert compute_sharpe_ratio(equity) > 0
