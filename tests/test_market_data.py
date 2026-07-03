from __future__ import annotations

import pandas as pd

from stock_trader.market_data import _normalize_index


def test_normalize_index_strips_timezone() -> None:
    aware = pd.date_range("2020-01-01", periods=5, freq="B", tz="America/New_York")
    naive = _normalize_index(aware)
    assert naive.tz is None
    assert len(naive) == 5
