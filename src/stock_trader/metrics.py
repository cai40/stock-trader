from __future__ import annotations

from stock_trader.models import OrderSide, Trade


def compute_max_drawdown(equity_curve: list[float]) -> float:
    if not equity_curve:
        return 0.0

    peak = equity_curve[0]
    max_drawdown = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
    return max_drawdown


def compute_win_rate(trades: list[Trade]) -> float:
    """Return the fraction of completed round-trip trades that were profitable."""
    by_symbol: dict[str, list[Trade]] = {}
    for trade in trades:
        by_symbol.setdefault(trade.symbol, []).append(trade)

    wins = 0
    round_trips = 0

    for symbol_trades in by_symbol.values():
        buy_cost = 0.0
        buy_qty = 0.0

        for trade in symbol_trades:
            if trade.side is OrderSide.BUY:
                buy_cost += trade.quantity * trade.price
                buy_qty += trade.quantity
            elif trade.side is OrderSide.SELL and buy_qty > 0:
                avg_cost = buy_cost / buy_qty
                if trade.price > avg_cost:
                    wins += 1
                round_trips += 1
                buy_cost = 0.0
                buy_qty = 0.0

    if round_trips == 0:
        return 0.0
    return wins / round_trips
