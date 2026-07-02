from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    timestamp: datetime


@dataclass(frozen=True)
class Order:
    symbol: str
    quantity: float
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    timestamp: datetime | None = None


@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    average_cost: float = 0.0

    @property
    def market_value(self) -> float:
        return self.quantity * self.average_cost

    def apply_fill(self, side: OrderSide, quantity: float, price: float) -> None:
        if quantity <= 0:
            raise ValueError("quantity must be positive")

        if side is OrderSide.BUY:
            total_cost = (self.quantity * self.average_cost) + (quantity * price)
            self.quantity += quantity
            self.average_cost = total_cost / self.quantity if self.quantity else 0.0
            return

        if quantity > self.quantity:
            raise ValueError("cannot sell more shares than held")

        self.quantity -= quantity
        if self.quantity == 0:
            self.average_cost = 0.0


@dataclass(frozen=True)
class Trade:
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    timestamp: datetime


SignalAction = Literal["buy", "sell", "hold"]


@dataclass(frozen=True)
class Signal:
    symbol: str
    action: SignalAction
    timestamp: datetime
    reason: str = ""


@dataclass
class BacktestResult:
    symbol: str
    strategy_name: str
    start_cash: float
    end_equity: float
    trades: list[Trade] = field(default_factory=list)
    max_drawdown: float = 0.0
    win_rate: float = 0.0

    @property
    def total_return(self) -> float:
        if self.start_cash == 0:
            return 0.0
        return (self.end_equity - self.start_cash) / self.start_cash

    @property
    def trade_count(self) -> int:
        return len(self.trades)


@dataclass
class PortfolioBacktestResult:
    symbols: list[str]
    strategy_name: str
    start_cash: float
    end_equity: float
    trades: list[Trade] = field(default_factory=list)
    max_drawdown: float = 0.0
    win_rate: float = 0.0

    @property
    def total_return(self) -> float:
        if self.start_cash == 0:
            return 0.0
        return (self.end_equity - self.start_cash) / self.start_cash

    @property
    def trade_count(self) -> int:
        return len(self.trades)
