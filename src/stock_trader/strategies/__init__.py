from __future__ import annotations

from stock_trader.strategies.base import Strategy
from stock_trader.strategies.rsi import RSIStrategy
from stock_trader.strategies.sma import MovingAverageCrossoverStrategy

STRATEGIES: dict[str, type[Strategy]] = {
    MovingAverageCrossoverStrategy.name: MovingAverageCrossoverStrategy,
    RSIStrategy.name: RSIStrategy,
}


def list_strategies() -> list[str]:
    return sorted(STRATEGIES)


def get_strategy(name: str, **kwargs) -> Strategy:
    try:
        strategy_cls = STRATEGIES[name]
    except KeyError as exc:
        available = ", ".join(sorted(STRATEGIES))
        raise ValueError(f"unknown strategy '{name}'. Available: {available}") from exc
    return strategy_cls(**kwargs)


__all__ = [
    "MovingAverageCrossoverStrategy",
    "RSIStrategy",
    "STRATEGIES",
    "Strategy",
    "get_strategy",
    "list_strategies",
]
