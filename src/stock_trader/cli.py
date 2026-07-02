from __future__ import annotations

import argparse
import sys

from stock_trader.backtest import BacktestEngine
from stock_trader.market_data import YFinanceMarketData
from stock_trader.strategies import get_strategy, list_strategies


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stock-trader",
        description="Paper trading and backtesting toolkit for stocks",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    quote_parser = subparsers.add_parser("quote", help="Fetch the latest quote for a symbol")
    quote_parser.add_argument("symbol", help="Ticker symbol, e.g. AAPL")

    strategies_parser = subparsers.add_parser("strategies", help="List available strategies")
    strategies_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show strategy class names",
    )

    backtest_parser = subparsers.add_parser("backtest", help="Run a historical backtest")
    backtest_parser.add_argument("symbol", help="Ticker symbol, e.g. AAPL")
    backtest_parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    backtest_parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    backtest_parser.add_argument(
        "--strategy",
        default="sma_crossover",
        help="Strategy name (default: sma_crossover)",
    )
    backtest_parser.add_argument(
        "--cash",
        type=float,
        default=10_000.0,
        help="Starting cash (default: 10000)",
    )

    paper_parser = subparsers.add_parser(
        "paper-trade",
        help="Run a paper-trade simulation with a shared portfolio",
    )
    paper_parser.add_argument("symbols", nargs="+", help="Ticker symbols")
    paper_parser.add_argument("--start", default="2023-01-01", help="Start date (YYYY-MM-DD)")
    paper_parser.add_argument("--end", default="2024-01-01", help="End date (YYYY-MM-DD)")
    paper_parser.add_argument(
        "--strategy",
        default="sma_crossover",
        help="Strategy name (default: sma_crossover)",
    )
    paper_parser.add_argument(
        "--cash",
        type=float,
        default=10_000.0,
        help="Starting cash for the shared portfolio (default: 10000)",
    )

    return parser


def cmd_quote(symbol: str) -> int:
    market_data = YFinanceMarketData()
    quote = market_data.get_quote(symbol)
    print(f"{quote.symbol}: ${quote.price:,.2f} @ {quote.timestamp.isoformat()}")
    return 0


def cmd_strategies(verbose: bool) -> int:
    from stock_trader.strategies import STRATEGIES

    for name in list_strategies():
        if verbose:
            print(f"{name:16}  {STRATEGIES[name].__name__}")
        else:
            print(name)
    return 0


def _print_result_summary(
    *,
    start_cash: float,
    end_equity: float,
    total_return: float,
    trade_count: int,
    max_drawdown: float,
    win_rate: float,
) -> None:
    print(f"Start cash:   ${start_cash:,.2f}")
    print(f"End equity:   ${end_equity:,.2f}")
    print(f"Total return: {total_return * 100:,.2f}%")
    print(f"Max drawdown: {max_drawdown * 100:,.2f}%")
    print(f"Win rate:     {win_rate * 100:,.1f}%")
    print(f"Trades:       {trade_count}")


def cmd_backtest(
    symbol: str,
    start: str,
    end: str,
    strategy_name: str,
    cash: float,
) -> int:
    market_data = YFinanceMarketData()
    strategy = get_strategy(strategy_name)
    engine = BacktestEngine(market_data)
    result = engine.run(symbol, strategy, start=start, end=end, initial_cash=cash)

    print(f"Symbol:       {result.symbol}")
    print(f"Strategy:     {result.strategy_name}")
    print(f"Period:       {start} to {end}")
    _print_result_summary(
        start_cash=result.start_cash,
        end_equity=result.end_equity,
        total_return=result.total_return,
        trade_count=result.trade_count,
        max_drawdown=result.max_drawdown,
        win_rate=result.win_rate,
    )
    return 0


def cmd_paper_trade(
    symbols: list[str],
    start: str,
    end: str,
    strategy_name: str,
    cash: float,
) -> int:
    market_data = YFinanceMarketData()
    strategy = get_strategy(strategy_name)
    engine = BacktestEngine(market_data)
    result = engine.run_portfolio(symbols, strategy, start=start, end=end, initial_cash=cash)

    print(f"Paper trading simulation ({strategy_name})")
    print(f"Symbols:  {', '.join(result.symbols)}")
    print(f"Period:   {start} to {end}\n")
    _print_result_summary(
        start_cash=result.start_cash,
        end_equity=result.end_equity,
        total_return=result.total_return,
        trade_count=result.trade_count,
        max_drawdown=result.max_drawdown,
        win_rate=result.win_rate,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "quote":
            return cmd_quote(args.symbol)
        if args.command == "strategies":
            return cmd_strategies(args.verbose)
        if args.command == "backtest":
            return cmd_backtest(args.symbol, args.start, args.end, args.strategy, args.cash)
        if args.command == "paper-trade":
            return cmd_paper_trade(args.symbols, args.start, args.end, args.strategy, args.cash)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
