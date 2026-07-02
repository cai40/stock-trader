#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python3 -m pip install -e ".[dev]"
echo ""
echo "Setup complete. Try:"
echo "  python3 -m pytest"
echo "  python3 -m stock_trader.cli strategies"
echo "  python3 -m stock_trader.cli quote AAPL"
