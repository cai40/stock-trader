from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from stock_trader.backtest import BacktestEngine
from stock_trader.market_data import MarketDataProvider
from stock_trader.metrics import compute_max_drawdown, compute_win_rate
from stock_trader.models import Order, OrderSide, Quote
from stock_trader.portfolio import Portfolio
from stock_trader.strategies import MovingAverageCrossoverStrategy, get_strategy, list_strategies
from stock_trader.strategies.rsi import RSIStrategy


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
