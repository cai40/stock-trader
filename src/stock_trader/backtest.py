from __future__ import annotations

from stock_trader.market_data import MarketDataProvider
from stock_trader.models import BacktestResult, Order, OrderSide, Quote
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

        price_lookup = {
            index.to_pydatetime(): float(row["Close"])
            for index, row in history.iterrows()
        }

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

        final_timestamp = history.index[-1].to_pydatetime()
        final_price = float(history.iloc[-1]["Close"])
        final_quote = Quote(symbol=symbol, price=final_price, timestamp=final_timestamp)

        return BacktestResult(
            symbol=symbol,
            strategy_name=strategy.name,
            start_cash=initial_cash,
            end_equity=portfolio.equity({symbol: final_quote}),
            trades=portfolio.trades,
        )
