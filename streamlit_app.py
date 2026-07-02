"""Streamlit Community Cloud entry point."""

import sys
from pathlib import Path

# Allow imports from src/ without an editable install on Streamlit Cloud.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from stock_trader.ui import main

main()
