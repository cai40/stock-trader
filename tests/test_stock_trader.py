from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from stock_trader.backtest import BacktestEngine
from stock_trader.market_data import MarketDataProvider
from stock_trader.metrics import compute_max_drawdown, compute_win_rate
from stock_trader.models import Order, OrderSide, Quote
from stock_trader.portfolio import Portfolio
from stock_trader.charts import strategy_label, strategy_summary
from stock_trader.dual_momentum import dual_momentum_equity
from stock_trader.vol_target import vol_target_equity
from stock_trader.strategies import (
    MovingAverageCrossoverStrategy,
    get_strategy,
    list_strategies,
)
from stock_trader.strategies.momentum import AbsoluteMomentumStrategy, TrendFilterStrategy
from stock_trader.strategies.rsi import RSIStrategy
from stock_trader.watchlist import label_to_symbol, watchlist_labels


class FakeMarketData:
    def __init__(self, histories: dict[str, pd.DataFrame], quote_price: float = 100.0) -> None:
        self.histories = histories
        self.quote_price = quote_price

    def get_quote(self, symbol: str) -> Quote:
        return Quote(symbol=symbol, price=self.quote_price, timestamp=datetime(2024, 1, 1))

    def get_history(
        self,
        symbol: str,
        start: str,
        end: str,
        interval: str = "1d",
    ) -> pd.DataFrame:
        return self.histories[symbol]


def make_trending_history() -> pd.DataFrame:
    prices = [
        50, 50, 50, 50, 50,
        55, 60, 65, 70, 75, 80, 85,
        80, 75, 70, 65, 60, 55, 50, 50, 50, 50, 50, 50,
    ]
    dates = pd.date_range("2024-01-01", periods=len(prices), freq="D")
    return pd.DataFrame({"Close": prices}, index=dates)


def make_rsi_swing_history() -> pd.DataFrame:
    prices = (
        [100] * 20
        + [95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40, 35, 30, 25]
        + [30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]
        + [105, 110, 115, 120, 125, 130, 135, 140, 145, 150]
        + [145, 140, 135, 130, 125, 120, 115, 110, 105, 100]
    )
    dates = pd.date_range("2024-01-01", periods=len(prices), freq="D")
    return pd.DataFrame({"Close": prices}, index=dates)


def test_watchlist_includes_requested_symbols() -> None:
    labels = watchlist_labels()
    symbols = {label_to_symbol(label) for label in labels}
    assert "VGT" in symbols
    assert "SPY" in symbols
    assert "TEL" in symbols


def test_portfolio_buy_and_sell_updates_cash_and_position() -> None:
    portfolio = Portfolio(cash=1_000.0)
    quote = Quote(symbol="AAPL", price=100.0, timestamp=datetime(2024, 1, 1))

    portfolio.execute(Order(symbol="AAPL", quantity=5, side=OrderSide.BUY), quote)
    assert portfolio.cash == 500.0
    assert portfolio.position("AAPL").quantity == 5.0

    portfolio.execute(Order(symbol="AAPL", quantity=2, side=OrderSide.SELL), quote)
    assert portfolio.cash == 700.0
    assert portfolio.position("AAPL").quantity == 3.0


def test_portfolio_rejects_insufficient_cash() -> None:
    portfolio = Portfolio(cash=100.0)
    quote = Quote(symbol="AAPL", price=100.0, timestamp=datetime(2024, 1, 1))

    with pytest.raises(ValueError, match="insufficient cash"):
        portfolio.execute(Order(symbol="AAPL", quantity=2, side=OrderSide.BUY), quote)


def test_moving_average_strategy_emits_buy_and_sell_signals() -> None:
    strategy = MovingAverageCrossoverStrategy(fast_window=3, slow_window=5)
    signals = strategy.generate_signals("TEST", make_trending_history())

    actions = [signal.action for signal in signals]
    assert "buy" in actions
    assert "sell" in actions


def test_rsi_strategy_emits_buy_and_sell_signals() -> None:
    strategy = RSIStrategy(period=5, oversold=30, overbought=70)
    signals = strategy.generate_signals("TEST", make_rsi_swing_history())

    actions = [signal.action for signal in signals]
    assert "buy" in actions
    assert "sell" in actions


def test_list_strategies_includes_builtin_strategies() -> None:
    names = list_strategies()
    assert "sma_crossover" in names
    assert "rsi" in names
    assert "ema_crossover" in names
    assert "macd" in names
    assert "bollinger" in names
    assert "absolute_momentum" in names
    assert "trend_filter" in names


def make_crash_recovery_history() -> pd.DataFrame:
    """Uptrend, sharp drawdown, then recovery — trend/momentum should exit before the worst."""
    prices = (
        [100 + i * 0.5 for i in range(260)]
        + [230 - i * 2 for i in range(60)]
        + [110 + i * 0.8 for i in range(120)]
    )
    dates = pd.date_range("2022-01-01", periods=len(prices), freq="B")
    return pd.DataFrame({"Close": prices}, index=dates)


def test_trend_filter_generates_buy_on_uptrend_cross() -> None:
    prices = [90] * 25 + [95, 100, 105, 110, 115, 120, 125, 130]
    dates = pd.date_range("2024-01-01", periods=len(prices), freq="D")
    history = pd.DataFrame({"Close": prices}, index=dates)
    strategy = TrendFilterStrategy(window=20)
    signals = strategy.generate_signals("TEST", history)
    assert any(signal.action == "buy" for signal in signals)


def test_absolute_momentum_rebalances_monthly() -> None:
    history = make_crash_recovery_history()
    strategy = AbsoluteMomentumStrategy(lookback=60)
    signals = strategy.generate_signals("TEST", history)
    assert signals
    assert all(signal.action in {"buy", "sell"} for signal in signals)


def test_dual_momentum_equity_curve() -> None:
    dates = pd.date_range("2022-01-01", periods=300, freq="B")
    risk = pd.DataFrame({"Close": [100 + i * 0.3 for i in range(300)]}, index=dates)
    safe = pd.DataFrame({"Close": [80 + i * 0.01 for i in range(300)]}, index=dates)

    equity = dual_momentum_equity(risk, safe, initial_cash=10_000.0, lookback=60)
    assert len(equity) == len(risk)
    assert float(equity.iloc[0]) > 0


def test_strategy_summary_returns_one_liner() -> None:
    text = strategy_summary("buy_and_hold")
    assert isinstance(text, str)
    assert len(text) > 10
    assert strategy_label("vol_target") == "Vol Target (15% target)"


def test_vol_target_equity_curve() -> None:
    dates = pd.date_range("2022-01-01", periods=120, freq="B")
    prices = [100 + i * 0.2 + (i % 10) for i in range(120)]
    history = pd.DataFrame({"Close": prices}, index=dates)

    equity = vol_target_equity(history, initial_cash=10_000.0)
    assert len(equity) == len(history)
    assert float(equity.iloc[0]) == 10_000.0
    assert float(equity.iloc[-1]) > 0


def test_compare_strategies_includes_vol_target() -> None:
    history = make_trending_history()
    market_data: MarketDataProvider = FakeMarketData({"TEST": history})
    engine = BacktestEngine(market_data)

    comparison = engine.compare_strategies(
        "TEST",
        start="2024-01-01",
        end="2024-01-31",
        initial_cash=10_000.0,
        strategy_names=["buy_and_hold", "vol_target"],
    )

    assert "vol_target" in comparison.curves
    assert len(comparison.curves["vol_target"]) == len(history)


def test_compare_strategies_includes_dual_momentum() -> None:
    history = make_trending_history()
    safe_history = pd.DataFrame({"Close": [50.0] * len(history)}, index=history.index)
    market_data: MarketDataProvider = FakeMarketData(
        {"TEST": history, "SHY": safe_history}
    )
    engine = BacktestEngine(market_data)

    comparison = engine.compare_strategies(
        "TEST",
        start="2024-01-01",
        end="2024-01-31",
        initial_cash=10_000.0,
        strategy_names=["buy_and_hold", "dual_momentum"],
    )

    assert "dual_momentum" in comparison.curves
    assert len(comparison.curves["dual_momentum"]) == len(history)


def test_backtest_returns_daily_equity_curve() -> None:
    history = make_trending_history()
    market_data: MarketDataProvider = FakeMarketData({"TEST": history})
    engine = BacktestEngine(market_data)
    strategy = MovingAverageCrossoverStrategy(fast_window=3, slow_window=5)

    result = engine.run(
        "TEST",
        strategy,
        start="2024-01-01",
        end="2024-01-31",
        initial_cash=10_000.0,
    )

    assert len(result.equity_curve) == len(history)
    assert float(result.equity_curve.iloc[0]) == 10_000.0


def test_compare_strategies_includes_buy_and_hold() -> None:
    history = make_trending_history()
    market_data: MarketDataProvider = FakeMarketData({"TEST": history})
    engine = BacktestEngine(market_data)

    comparison = engine.compare_strategies(
        "TEST",
        start="2024-01-01",
        end="2024-01-31",
        initial_cash=10_000.0,
        strategy_names=["buy_and_hold", "sma_crossover"],
    )

    assert "buy_and_hold" in comparison.curves
    assert "sma_crossover" in comparison.curves
    assert len(comparison.curves["buy_and_hold"]) == len(history)


def test_get_strategy_returns_rsi() -> None:
    strategy = get_strategy("rsi")
    assert strategy.name == "rsi"


def test_backtest_engine_runs_with_fake_market_data() -> None:
    history = make_trending_history()
    market_data: MarketDataProvider = FakeMarketData({"TEST": history})
    engine = BacktestEngine(market_data)
    strategy = MovingAverageCrossoverStrategy(fast_window=3, slow_window=5)

    result = engine.run(
        "TEST",
        strategy,
        start="2024-01-01",
        end="2024-01-31",
        initial_cash=10_000.0,
    )

    assert result.symbol == "TEST"
    assert result.end_equity > 0
    assert result.trade_count >= 1
    assert result.max_drawdown >= 0
    assert 0 <= result.win_rate <= 1


def test_backtest_engine_shared_portfolio_uses_single_cash_pool() -> None:
    history = make_trending_history()
    market_data: MarketDataProvider = FakeMarketData(
        {
            "AAA": history,
            "BBB": history,
        }
    )
    engine = BacktestEngine(market_data)
    strategy = MovingAverageCrossoverStrategy(fast_window=3, slow_window=5)

    result = engine.run_portfolio(
        ["AAA", "BBB"],
        strategy,
        start="2024-01-01",
        end="2024-01-31",
        initial_cash=10_000.0,
    )

    assert result.symbols == ["AAA", "BBB"]
    assert result.start_cash == 10_000.0
    assert result.trade_count >= 1


def test_compute_max_drawdown() -> None:
    assert compute_max_drawdown([100, 120, 90, 110]) == pytest.approx(0.25)


def test_compute_win_rate_counts_profitable_round_trips() -> None:
    portfolio = Portfolio(cash=1_000.0)
    buy_quote = Quote(symbol="AAPL", price=100.0, timestamp=datetime(2024, 1, 1))
    sell_quote = Quote(symbol="AAPL", price=120.0, timestamp=datetime(2024, 1, 2))
    portfolio.execute(Order(symbol="AAPL", quantity=1, side=OrderSide.BUY), buy_quote)
    portfolio.execute(Order(symbol="AAPL", quantity=1, side=OrderSide.SELL), sell_quote)

    assert compute_win_rate(portfolio.trades) == 1.0
