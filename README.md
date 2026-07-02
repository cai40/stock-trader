# Stock Trader

Standalone Python project for **paper trading**, **market data**, and **strategy backtesting**. Fetch historical prices, run strategies, and simulate trades without risking real capital.

## Features

- Portfolio and order management with cash tracking
- Historical market data via [yfinance](https://github.com/ranaroussi/yfinance)
- Pluggable strategies (moving-average crossover and RSI included)
- Backtesting engine with performance summary (return, drawdown, win rate)
- CLI for quotes, backtests, paper-trade simulation, and strategy listing
- **Web UI** (Streamlit) for mobile-friendly browser access

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

### Web UI (browser app)

Install UI dependencies and launch the app:

```bash
pip install -e ".[ui]"
python3 -m streamlit run src/stock_trader/ui.py --server.address 0.0.0.0 --server.port 8501
```

Open the URL shown in the terminal (port **8501**). Works on iPhone Safari when the server is reachable (Cursor web, Codespaces, etc.).

**If the direct URL doesn't load** (cloud VMs block public ports), run:

```bash
bash scripts/start-ui.sh
```

This starts Streamlit and prints a public `http://bore.pub:PORT` link you can open on your iPhone.

**Permanent hosting (recommended):** deploy free on [Streamlit Community Cloud](https://share.streamlit.io):
1. Merge this repo to `main`
2. Go to share.streamlit.io → New app → select `cai40/stock-trader`
3. Main file: `streamlit_app.py`, requirements: `requirements-ui.txt`
4. You get a stable URL like `https://stock-trader.streamlit.app`

Tabs: **Quote** · **Backtest** · **Paper trade**

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

## Test from iPhone (no Mac or PC)

This project is a Python CLI, not a native iOS app. To run it from a phone browser, use a **cloud dev environment** — the code runs on a remote machine; your phone is the screen and keyboard.

### Option A: GitHub Codespaces (Safari on iPhone)

1. Open **https://github.com/cai40/stock-trader** in Safari.
2. Sign in to GitHub.
3. Tap **Code** → **Codespaces** → **Create codespace on main**.
4. Wait for the browser IDE to load (setup runs automatically).
5. Open the **Terminal** panel and run:

```bash
python3 -m pytest
python3 -m stock_trader.cli strategies
python3 -m stock_trader.cli quote AAPL
python3 -m stock_trader.cli backtest AAPL --start 2023-01-01 --end 2024-01-01
```

> **Note:** Codespaces requires a GitHub account. Free tier includes limited monthly hours.

### Option B: Cursor web (you are here)

If you opened this repo in **cursor.com/agents** or the Cursor web app:

1. Open the **terminal** in the web UI.
2. Run the one-time setup:

```bash
bash scripts/setup.sh
```

3. Then run any command:

```bash
python3 -m pytest
python3 -m stock_trader.cli quote AAPL
```

Cloud Agents can also run these commands for you — just ask in the agent chat.

## Disclaimer

Stock Trader is for **educational and research purposes only**. It does not connect to live brokerages and is not financial advice. Past backtest performance does not guarantee future results.
