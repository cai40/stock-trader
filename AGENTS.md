# AGENTS.md

Instructions for Cursor Cloud Agents working on the **stock-trader** repository.

## Project overview

Python toolkit for paper trading, market data, and strategy backtesting. Uses `yfinance` for live quotes and historical OHLCV data. No broker integration — educational/research use only.

## Environment setup

Cloud Agent VMs have Python 3.12 but `python` may not be on `PATH`. Use `python3` explicitly.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python3 -m pytest
```

| Task | Command |
|------|---------|
| Install | `pip install -e ".[dev]"` |
| Run tests | `python3 -m pytest` |
| CLI help | `python3 -m stock_trader.cli --help` |
| Quote | `python3 -m stock_trader.cli quote AAPL` |
| Backtest | `python3 -m stock_trader.cli backtest AAPL --start 2023-01-01 --end 2024-01-01` |
| Paper trade | `python3 -m stock_trader.cli paper-trade AAPL MSFT --cash 10000` |
| List strategies | `python3 -m stock_trader.cli strategies` |
| **Web UI** | `python3 -m streamlit run src/stock_trader/ui.py --server.address 0.0.0.0 --server.port 8501` |

No secrets or API keys are required — `yfinance` is unauthenticated.

## Architecture

```
src/stock_trader/
├── cli.py              # argparse CLI entry point
├── models.py           # Order, Position, Trade, Signal, BacktestResult
├── portfolio.py        # cash/position tracking and order execution
├── market_data.py      # MarketDataProvider protocol + YFinanceMarketData
├── backtest.py         # BacktestEngine (single- and multi-symbol)
├── metrics.py          # drawdown, win-rate helpers
└── strategies/         # pluggable Strategy subclasses
```

## Coding conventions

- Python 3.10+ type hints throughout
- `dataclasses` for domain models; `Protocol` for interfaces
- Strategies register in `strategies/__init__.py` via `STRATEGIES` dict
- Tests use fake market data — no network calls in `tests/`
- Keep changes minimal and focused; match existing style

## Deployment (Render)

**Render deploys from `main` only.** A commit on a feature branch (`cursor/...-51aa`) or an open PR does **not** update the live site. The user will not see changes on Render until they land on `main`.

### Required workflow for UI / deploy-visible work

When the task affects the Streamlit app or anything the user checks on Render:

1. Implement and test on a feature branch (`cursor/<descriptive-name>-51aa`).
2. Commit and push the branch; open or update a PR if useful for review.
3. **Merge into `main` and push `origin main`** — this step is mandatory before marking the task done.
4. Confirm `origin/main` contains the commit (e.g. `git log origin/main -1`).
5. Tell the user to **Manual Deploy** on Render if auto-deploy did not run.

Do **not** stop after pushing only a feature branch and report success. That leaves Render on the previous `main` commit.

```bash
git checkout main
git pull origin main
git merge cursor/<descriptive-name>-51aa
git push origin main
```

Auto-deploy on Render is unreliable; always mention Manual Deploy when shipping UI changes.

## Roadmap

Track progress here. Mark items `[x]` when done.

- [x] Initial scaffold: portfolio, SMA crossover, CLI, tests, CI
- [x] Add AGENTS.md with setup and architecture docs
- [x] Shared-portfolio paper trading (single cash pool across symbols)
- [x] RSI momentum strategy
- [x] `strategies` CLI subcommand to list available strategies
- [x] Backtest performance metrics: max drawdown and win rate
- [x] Tests for new features

## Security notes

- Never commit real credentials — this project needs none
- `yfinance` calls external APIs at runtime; tests must not depend on them

## Cursor Cloud specific instructions

- Dependencies are installed automatically by the startup update script into `.venv` (the image already has the `python3.12-venv` module). Activate with `source .venv/bin/activate` before running any `stock-trader` / `python3 -m stock_trader.cli` / `streamlit` command.
- Run the Streamlit UI bound to all interfaces so the cloud preview can reach it: `python3 -m streamlit run src/stock_trader/ui.py --server.address 0.0.0.0 --server.port 8501 --server.headless true`. Liveness probe: `GET /_stcore/health` returns `ok`.
- Network egress works here, so `yfinance` live quotes and backtests succeed (verified). Tests use fake data and never hit the network.
