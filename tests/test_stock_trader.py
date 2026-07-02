from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from stock_trader.backtest import BacktestEngine
from stock_trader.market_data import MarketDataProvider
from stock_trader.models import Order, OrderSide, Quote
from stock_trader.portfolio import Portfolio
from stock_trader.strategies import MovingAverageCrossoverStrategy


class FakeMarketData:
    def __init__(self, history: pd.DataFrame, quote_price: float = 100.0) -> None:
        self.history = history
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
        return self.history


def make_trending_history() -> pd.DataFrame:
    prices = [
        50, 50, 50, 50, 50,
        55, 60, 65, 70, 75, 80, 85,
        80, 75, 70, 65, 60, 55, 50, 50, 50, 50, 50, 50,
    ]
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


def test_backtest_engine_runs_with_fake_market_data() -> None:
    history = make_trending_history()
    market_data: MarketDataProvider = FakeMarketData(history)
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
