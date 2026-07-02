from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from stock_trader.models import Order, OrderSide, Position, Quote, Trade


@dataclass
class Portfolio:
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    trades: list[Trade] = field(default_factory=list)

    def position(self, symbol: str) -> Position:
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol)
        return self.positions[symbol]

    def equity(self, quotes: dict[str, Quote]) -> float:
        holdings_value = sum(
            position.quantity * quotes[symbol].price
            for symbol, position in self.positions.items()
            if position.quantity > 0 and symbol in quotes
        )
        return self.cash + holdings_value

    def execute(self, order: Order, quote: Quote) -> Trade:
        if order.symbol != quote.symbol:
            raise ValueError("order symbol does not match quote symbol")

        timestamp = order.timestamp or quote.timestamp
        price = quote.price
        position = self.position(order.symbol)

        if order.side is OrderSide.BUY:
            cost = order.quantity * price
            if cost > self.cash:
                raise ValueError("insufficient cash for buy order")
            self.cash -= cost
            position.apply_fill(OrderSide.BUY, order.quantity, price)
        else:
            proceeds = order.quantity * price
            position.apply_fill(OrderSide.SELL, order.quantity, price)
            self.cash += proceeds

        trade = Trade(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=price,
            timestamp=timestamp,
        )
        self.trades.append(trade)
        return trade

    def max_buy_quantity(self, symbol: str, price: float) -> float:
        if price <= 0:
            return 0.0
        return self.cash // price
