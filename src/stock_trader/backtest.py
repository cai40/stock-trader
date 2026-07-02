from __future__ import annotations

from datetime import datetime

import pandas as pd

from stock_trader.market_data import MarketDataProvider
from stock_trader.metrics import compute_max_drawdown, compute_win_rate
from stock_trader.models import (
    BacktestResult,
    Order,
    OrderSide,
    PortfolioBacktestResult,
    Quote,
    Signal,
)
from stock_trader.portfolio import Portfolio
from stock_trader.strategies import Strategy


class BacktestEngine:
    def __init__(self, market_data: MarketDataProvider) -> None:
        self.market_data = market_data

    def run(
        self,
        symbol: str,
        strategy: Strategy,
        start: str,
        end: str,
        initial_cash: float = 10_000.0,
    ) -> BacktestResult:
        history = self.market_data.get_history(symbol, start=start, end=end)
        signals = strategy.generate_signals(symbol, history)
        portfolio = Portfolio(cash=initial_cash)
        price_lookup = self._price_lookup(history)

        equity_curve = self._execute_signals(
            portfolio,
            symbol,
            signals,
            price_lookup,
            initial_cash,
        )

        final_timestamp = history.index[-1].to_pydatetime()
        final_price = float(history.iloc[-1]["Close"])
        final_quote = Quote(symbol=symbol, price=final_price, timestamp=final_timestamp)
        end_equity = portfolio.equity({symbol: final_quote})
        equity_curve.append(end_equity)

        return BacktestResult(
            symbol=symbol,
            strategy_name=strategy.name,
            start_cash=initial_cash,
            end_equity=end_equity,
            trades=portfolio.trades,
            max_drawdown=compute_max_drawdown(equity_curve),
            win_rate=compute_win_rate(portfolio.trades),
        )

    def run_portfolio(
        self,
        symbols: list[str],
        strategy: Strategy,
        start: str,
        end: str,
        initial_cash: float = 10_000.0,
    ) -> PortfolioBacktestResult:
        portfolio = Portfolio(cash=initial_cash)
        histories: dict[str, pd.DataFrame] = {}
        price_lookups: dict[str, dict[datetime, float]] = {}
        events: list[tuple[datetime, str, Signal]] = []

        for symbol in symbols:
            history = self.market_data.get_history(symbol, start=start, end=end)
            histories[symbol] = history
            price_lookups[symbol] = self._price_lookup(history)
            for signal in strategy.generate_signals(symbol, history):
                events.append((signal.timestamp, symbol, signal))

        events.sort(key=lambda item: item[0])
        equity_curve = [initial_cash]
        last_prices: dict[str, float] = {}

        for timestamp, symbol, signal in events:
            price = price_lookups[symbol].get(timestamp)
            if price is None:
                continue

            last_prices[symbol] = price
            quote = Quote(symbol=symbol, price=price, timestamp=timestamp)
            position = portfolio.position(symbol)

            if signal.action == "buy":
                quantity = portfolio.max_buy_quantity(symbol, price)
                if quantity <= 0:
                    continue
                portfolio.execute(
                    Order(
                        symbol=symbol,
                        quantity=quantity,
                        side=OrderSide.BUY,
                        timestamp=timestamp,
                    ),
                    quote,
                )
            elif signal.action == "sell" and position.quantity > 0:
                portfolio.execute(
                    Order(
                        symbol=symbol,
                        quantity=position.quantity,
                        side=OrderSide.SELL,
                        timestamp=timestamp,
                    ),
                    quote,
                )

            equity_curve.append(
                portfolio.equity(self._quotes_at_timestamp(last_prices, timestamp))
            )

        final_quotes = {
            symbol: Quote(
                symbol=symbol,
                price=float(histories[symbol].iloc[-1]["Close"]),
                timestamp=histories[symbol].index[-1].to_pydatetime(),
            )
            for symbol in symbols
        }
        end_equity = portfolio.equity(final_quotes)
        equity_curve.append(end_equity)

        return PortfolioBacktestResult(
            symbols=symbols,
            strategy_name=strategy.name,
            start_cash=initial_cash,
            end_equity=end_equity,
            trades=portfolio.trades,
            max_drawdown=compute_max_drawdown(equity_curve),
            win_rate=compute_win_rate(portfolio.trades),
        )

    def _price_lookup(self, history: pd.DataFrame) -> dict[datetime, float]:
        return {
            index.to_pydatetime(): float(row["Close"])
            for index, row in history.iterrows()
        }

    def _execute_signals(
        self,
        portfolio: Portfolio,
        symbol: str,
        signals: list[Signal],
        price_lookup: dict[datetime, float],
        initial_cash: float,
    ) -> list[float]:
        equity_curve = [initial_cash]

        for signal in signals:
            price = price_lookup.get(signal.timestamp)
            if price is None:
                continue

            quote = Quote(symbol=symbol, price=price, timestamp=signal.timestamp)
            position = portfolio.position(symbol)

            if signal.action == "buy":
                quantity = portfolio.max_buy_quantity(symbol, price)
                if quantity <= 0:
                    continue
                portfolio.execute(
                    Order(
                        symbol=symbol,
                        quantity=quantity,
                        side=OrderSide.BUY,
                        timestamp=signal.timestamp,
                    ),
                    quote,
                )
            elif signal.action == "sell" and position.quantity > 0:
                portfolio.execute(
                    Order(
                        symbol=symbol,
                        quantity=position.quantity,
                        side=OrderSide.SELL,
                        timestamp=signal.timestamp,
                    ),
                    quote,
                )

            equity_curve.append(portfolio.equity({symbol: quote}))

        return equity_curve

    @staticmethod
    def _quotes_at_timestamp(
        last_prices: dict[str, float],
        timestamp: datetime,
    ) -> dict[str, Quote]:
        return {
            symbol: Quote(symbol=symbol, price=price, timestamp=timestamp)
            for symbol, price in last_prices.items()
        }
