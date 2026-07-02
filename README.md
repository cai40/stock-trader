# Stock Trader

Standalone Python project for **paper trading**, **market data**, and **strategy backtesting**. Fetch historical prices, run strategies, and simulate trades without risking real capital.

## Features

- Portfolio and order management with cash tracking
- Historical market data via [yfinance](https://github.com/ranaroussi/yfinance)
- Pluggable strategies (moving-average crossover and RSI included)
- Backtesting engine with performance summary (return, drawdown, win rate)
- CLI for quotes, backtests, paper-trade simulation, and strategy listing

## Quick start

```bash
cd stock-trader
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Fetch a quote

```bash
stock-trader quote AAPL
```

### Run a backtest

```bash
stock-trader backtest AAPL --start 2023-01-01 --end 2024-01-01 --strategy sma_crossover
```

### List strategies

```bash
stock-trader strategies
```

### Simulate paper trading

```bash
stock-trader paper-trade AAPL MSFT --cash 10000 --strategy sma_crossover
```

Paper trading uses a **shared portfolio** — one cash pool across all symbols.

## Project layout

```
stock-trader/
├── src/stock_trader/
│   ├── cli.py              # Command-line interface
│   ├── models.py           # Orders, positions, trades
│   ├── portfolio.py        # Portfolio and execution
│   ├── market_data.py      # yfinance data provider
│   ├── backtest.py         # Backtesting engine
│   ├── metrics.py          # Drawdown and win-rate helpers
│   └── strategies/         # Trading strategies
├── AGENTS.md               # Cloud Agent instructions
├── tests/
├── pyproject.toml
└── README.md
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Disclaimer

Stock Trader is for **educational and research purposes only**. It does not connect to live brokerages and is not financial advice. Past backtest performance does not guarantee future results.
