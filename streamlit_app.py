"""Streamlit Community Cloud entry point — v0.2.2 (stock dropdown watchlist)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

# Ensure watchlist module is present (fail loud on stale/missing deploy).
WATCHLIST_FILE = ROOT / "src" / "stock_trader" / "watchlist.py"
if not WATCHLIST_FILE.exists():
    import streamlit as st

    st.error("Deploy is missing watchlist.py. Tap **Manage app → Reboot app** to redeploy from GitHub.")
    st.stop()

from stock_trader.ui import APP_VERSION, main

assert APP_VERSION == "0.2.2", f"Stale build {APP_VERSION}; reboot the app on Streamlit Cloud."

main()
