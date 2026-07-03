from __future__ import annotations

from datetime import datetime

import pandas as pd

from stock_trader.benchmarks import buy_and_hold_equity, equity_metrics
from stock_trader.dual_momentum import dual_momentum_equity
from stock_trader.vol_target import vol_target_equity
from stock_trader.market_data import MarketDataProvider
from stock_trader.metrics import compute_max_drawdown, compute_win_rate
from stock_trader.models import (
    BacktestResult,
    Order,
    OrderSide,
    PortfolioBacktestResult,
    Quote,
    Signal,
    StrategyComparison,
)
from stock_trader.portfolio import Portfolio
from stock_trader.strategies import Strategy, get_strategy, list_strategies

WARMUP_CALENDAR_DAYS = 400


def _warmup_start(start: str) -> str:
    return (pd.Timestamp(start) - pd.Timedelta(days=WARMUP_CALENDAR_DAYS)).strftime("%Y-%m-%d")


def _rebase_equity(equity: pd.Series, initial_cash: float) -> pd.Series:
    if equity.empty:
        return equity
    start_value = float(equity.iloc[0])
    if start_value == 0:
        return equity
    return equity / start_value * initial_cash


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
        history: pd.DataFrame | None = None,
    ) -> BacktestResult:
        if history is None:
            history = self.market_data.get_history(
                symbol, start=_warmup_start(start), end=end
            )
        result = self._run_on_history(symbol, strategy, history, initial_cash)
        return self._trim_result(result, start)

    def _trim_result(self, result: BacktestResult, start: str) -> BacktestResult:
        start_ts = pd.Timestamp(start)
        trimmed = result.equity_curve.loc[result.equity_curve.index >= start_ts]
        if trimmed.empty:
            return result

        trimmed = _rebase_equity(trimmed, result.start_cash)

        trades = [trade for trade in result.trades if trade.timestamp >= start_ts.to_pydatetime()]
        return BacktestResult(
            symbol=result.symbol,
            strategy_name=result.strategy_name,
            start_cash=result.start_cash,
            end_equity=float(trimmed.iloc[-1]),
            trades=trades,
            max_drawdown=compute_max_drawdown(trimmed.tolist()),
            win_rate=compute_win_rate(trades),
            equity_curve=trimmed,
        )

    def _run_on_history(
        self,
        symbol: str,
        strategy: Strategy,
        history: pd.DataFrame,
        initial_cash: float,
    ) -> BacktestResult:
        signals = strategy.generate_signals(symbol, history)
        portfolio, equity_curve = self._simulate_daily(
            symbol=symbol,
            history=history,
            signals=signals,
            initial_cash=initial_cash,
        )

        end_equity = float(equity_curve.iloc[-1]) if not equity_curve.empty else initial_cash

        return BacktestResult(
            symbol=symbol,
            strategy_name=strategy.name,
            start_cash=initial_cash,
            end_equity=end_equity,
            trades=portfolio.trades,
            max_drawdown=compute_max_drawdown(equity_curve.tolist()),
            win_rate=compute_win_rate(portfolio.trades),
            equity_curve=equity_curve,
        )

    def compare_strategies(
        self,
        symbol: str,
        start: str,
        end: str,
        initial_cash: float = 10_000.0,
        strategy_names: list[str] | None = None,
    ) -> StrategyComparison:
        full_history = self.market_data.get_history(
            symbol, start=_warmup_start(start), end=end
        )
        start_ts = pd.Timestamp(start)
        history = full_history.loc[full_history.index >= start_ts]
        names = strategy_names or (["buy_and_hold", *list_strategies()])

        curves: dict[str, pd.Series] = {}
        results: dict[str, BacktestResult] = {}

        safe_history: pd.DataFrame | None = None

        for name in names:
            if name == "buy_and_hold":
                buy_hold = _rebase_equity(buy_and_hold_equity(history, initial_cash), initial_cash)
                end_equity, max_dd = equity_metrics(buy_hold, initial_cash)
                curves[name] = buy_hold
                results[name] = BacktestResult(
                    symbol=symbol,
                    strategy_name="buy_and_hold",
                    start_cash=initial_cash,
                    end_equity=end_equity,
                    max_drawdown=max_dd,
                    equity_curve=buy_hold,
                )
                continue

            if name == "dual_momentum":
                if safe_history is None:
                    safe_history = self.market_data.get_history(
                        "SHY", start=_warmup_start(start), end=end
                    )
                equity = dual_momentum_equity(full_history, safe_history, initial_cash)
                equity = _rebase_equity(equity.loc[equity.index >= start_ts], initial_cash)
                end_equity = float(equity.iloc[-1]) if not equity.empty else initial_cash
                curves[name] = equity
                results[name] = BacktestResult(
                    symbol=symbol,
                    strategy_name="dual_momentum",
                    start_cash=initial_cash,
                    end_equity=end_equity,
                    max_drawdown=compute_max_drawdown(equity.tolist()),
                    equity_curve=equity,
                )
                continue

            if name == "vol_target":
                equity = vol_target_equity(full_history, initial_cash)
                equity = _rebase_equity(equity.loc[equity.index >= start_ts], initial_cash)
                end_equity = float(equity.iloc[-1]) if not equity.empty else initial_cash
                curves[name] = equity
                results[name] = BacktestResult(
                    symbol=symbol,
                    strategy_name="vol_target",
                    start_cash=initial_cash,
                    end_equity=end_equity,
                    max_drawdown=compute_max_drawdown(equity.tolist()),
                    equity_curve=equity,
                )
                continue

            result = self.run(
                symbol,
                get_strategy(name),
                start,
                end,
                initial_cash,
                history=full_history,
            )
            curves[name] = result.equity_curve
            results[name] = result

        return StrategyComparison(
            symbol=symbol,
            start=start,
            end=end,
            start_cash=initial_cash,
            curves=curves,
            results=results,
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

    def _simulate_daily(
        self,
        symbol: str,
        history: pd.DataFrame,
        signals: list[Signal],
        initial_cash: float,
    ) -> tuple[Portfolio, pd.Series]:
        portfolio = Portfolio(cash=initial_cash)
        signals_by_ts = {signal.timestamp: signal for signal in signals}
        equities: list[float] = []

        for timestamp, row in history.iterrows():
            dt = timestamp.to_pydatetime()
            price = float(row["Close"])
            quote = Quote(symbol=symbol, price=price, timestamp=dt)

            signal = signals_by_ts.get(dt)
            if signal is not None:
                position = portfolio.position(symbol)
                if signal.action == "buy":
                    quantity = portfolio.max_buy_quantity(symbol, price)
                    if quantity > 0:
                        portfolio.execute(
                            Order(
                                symbol=symbol,
                                quantity=quantity,
                                side=OrderSide.BUY,
                                timestamp=dt,
                            ),
                            quote,
                        )
                elif signal.action == "sell" and position.quantity > 0:
                    portfolio.execute(
                        Order(
                            symbol=symbol,
                            quantity=position.quantity,
                            side=OrderSide.SELL,
                            timestamp=dt,
                        ),
                        quote,
                    )

            equities.append(portfolio.equity({symbol: quote}))

        equity_curve = pd.Series(equities, index=history.index)
        return portfolio, equity_curve

    def _price_lookup(self, history: pd.DataFrame) -> dict[datetime, float]:
        return {
            index.to_pydatetime(): float(row["Close"])
            for index, row in history.iterrows()
        }

    @staticmethod
    def _quotes_at_timestamp(
        last_prices: dict[str, float],
        timestamp: datetime,
    ) -> dict[str, Quote]:
        return {
            symbol: Quote(symbol=symbol, price=price, timestamp=timestamp)
            for symbol, price in last_prices.items()
        }
