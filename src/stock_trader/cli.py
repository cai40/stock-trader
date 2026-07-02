from __future__ import annotations

import argparse
import sys

from stock_trader.backtest import BacktestEngine
from stock_trader.market_data import YFinanceMarketData
from stock_trader.strategies import get_strategy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stock-trader",
        description="Paper trading and backtesting toolkit for stocks",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    quote_parser = subparsers.add_parser("quote", help="Fetch the latest quote for a symbol")
    quote_parser.add_argument("symbol", help="Ticker symbol, e.g. AAPL")

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
        help="Run a paper-trade backtest across multiple symbols",
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
        help="Starting cash per symbol (default: 10000)",
    )

    return parser


def cmd_quote(symbol: str) -> int:
    market_data = YFinanceMarketData()
    quote = market_data.get_quote(symbol)
    print(f"{quote.symbol}: ${quote.price:,.2f} @ {quote.timestamp.isoformat()}")
    return 0


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
    print(f"Start cash:   ${result.start_cash:,.2f}")
    print(f"End equity:   ${result.end_equity:,.2f}")
    print(f"Total return: {result.total_return * 100:,.2f}%")
    print(f"Trades:       {result.trade_count}")
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

    print(f"Paper trading simulation ({strategy_name})")
    print(f"Period: {start} to {end}\n")

    for symbol in symbols:
        result = engine.run(symbol, strategy, start=start, end=end, initial_cash=cash)
        print(
            f"{result.symbol:6}  "
            f"equity=${result.end_equity:>10,.2f}  "
            f"return={result.total_return * 100:>7.2f}%  "
            f"trades={result.trade_count}"
        )

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "quote":
            return cmd_quote(args.symbol)
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
