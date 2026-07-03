from __future__ import annotations

import pandas as pd
import pytest

from stock_trader.crash_warning import (
    HISTORICAL_CRASHES,
    RiskLevel,
    _download_panel,
    assess_crash_risk,
    composite_score_chart,
    composite_score_monthly,
    composite_score_series,
    compute_crash_features,
    crashes_in_range,
    load_crash_panel,
    nasdaq_normalized,
)
from stock_trader.charts import crash_warning_nasdaq_figure


class FakeMarketData:
    def __init__(self, panel: pd.DataFrame) -> None:
        self.panel = panel

    def get_history(self, symbol: str, start: str, end: str, interval: str = "1d") -> pd.DataFrame:
        ticker_map = {
            "SPY": "SPY",
            "^IXIC": "IXIC",
            "^VIX": "VIX",
            "^TNX": "TNX",
            "^IRX": "IRX",
            "HYG": "HYG",
            "LQD": "LQD",
            "IWM": "IWM",
        }
        name = ticker_map.get(symbol, symbol)
        sub = self.panel.loc[start:end]
        return pd.DataFrame({"Close": sub[name]})


def _rising_panel(rows: int = 400) -> pd.DataFrame:
    dates = pd.date_range("2018-01-01", periods=rows, freq="B")
    return pd.DataFrame(
        {
            "SPY": [100 + i * 0.2 for i in range(rows)],
            "VIX": [14 + (i % 5) for i in range(rows)],
            "TNX": [3.0 + i * 0.001 for i in range(rows)],
            "IRX": [1.0 + i * 0.0005 for i in range(rows)],
            "HYG": [75 + i * 0.05 for i in range(rows)],
            "LQD": [100 + i * 0.04 for i in range(rows)],
            "IWM": [90 + i * 0.15 for i in range(rows)],
            "IXIC": [200 + i * 0.25 for i in range(rows)],
        },
        index=dates,
    )


def _stress_panel(rows: int = 400) -> pd.DataFrame:
    dates = pd.date_range("2018-01-01", periods=rows, freq="B")
    spy = [200.0] * 300 + [170.0 - i * 0.3 for i in range(100)]
    return pd.DataFrame(
        {
            "SPY": spy,
            "VIX": [15.0] * 300 + [35.0 + i * 0.1 for i in range(100)],
            "TNX": [2.0] * 200 + [4.0] * 100 + [1.5] * 100,
            "IRX": [4.5] * 200 + [4.0] * 100 + [4.8] * 100,
            "HYG": [80.0] * 300 + [65.0 - i * 0.05 for i in range(100)],
            "LQD": [110.0] * 300 + [112.0 + i * 0.02 for i in range(100)],
            "IWM": [100.0] * 300 + [75.0 - i * 0.2 for i in range(100)],
            "IXIC": [300.0] * 300 + [220.0 - i * 0.4 for i in range(100)],
        },
        index=dates,
    )


def test_compute_crash_features_columns() -> None:
    panel = _rising_panel()
    features = compute_crash_features(panel)
    assert "vix_rvol_spread" in features.columns
    assert "yc_inverted" in features.columns
    assert len(features) == len(panel)


def test_assess_crash_risk_risk_on_in_calm_market() -> None:
    features = compute_crash_features(_rising_panel()).dropna()
    assessment = assess_crash_risk(features)
    assert assessment.risk_level is RiskLevel.RISK_ON
    assert assessment.active_count < 3


def test_assess_crash_risk_elevated_in_stress_market() -> None:
    features = compute_crash_features(_stress_panel()).dropna()
    assessment = assess_crash_risk(features)
    assert assessment.active_count >= 3
    assert assessment.risk_level in {RiskLevel.CAUTION, RiskLevel.DEFENSIVE, RiskLevel.CRITICAL}


def test_composite_score_series_length() -> None:
    features = compute_crash_features(_rising_panel()).dropna()
    scores = composite_score_monthly(features)
    assert len(scores) <= len(features)
    assert len(scores) >= 1
    assert float(scores.iloc[-1]) >= 0


def test_composite_score_monthly_one_point_per_month() -> None:
    features = compute_crash_features(_rising_panel()).dropna()
    monthly = composite_score_monthly(features)
    months = monthly.index.to_period("M")
    assert len(months) == len(months.unique())


def test_composite_score_chart_fewer_points_than_daily() -> None:
    features = compute_crash_features(_rising_panel()).dropna()
    chart = composite_score_chart(features)
    assert len(chart) < len(features)
    assert len(chart) >= 1


def test_load_crash_panel_with_fake_data() -> None:
    panel = _rising_panel()
    _, features, assessment = load_crash_panel(
        "2019-01-01",
        "2019-12-31",
        FakeMarketData(panel),
    )
    assert not features.empty
    assert assessment.as_of == features.index[-1]


def test_assess_crash_risk_empty_features_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        assess_crash_risk(pd.DataFrame())


def test_nasdaq_normalized_starts_at_100() -> None:
    panel = _rising_panel()
    series = nasdaq_normalized(panel, pd.Timestamp("2018-06-01"))
    assert not series.empty
    assert series.iloc[0] == pytest.approx(100.0)


def test_crashes_in_range_filters_events() -> None:
    events = crashes_in_range(pd.Timestamp("2007-01-01"), pd.Timestamp("2010-01-01"))
    names = {e.name for e in events}
    assert "Global Financial Crisis" in names
    assert "Dot-com bust" not in names


def test_crash_warning_nasdaq_figure_builds() -> None:
    panel = _rising_panel()
    features = compute_crash_features(panel).dropna()
    score = composite_score_chart(features)
    nasdaq = nasdaq_normalized(panel, panel.index[0])
    events = list(HISTORICAL_CRASHES)
    fig = crash_warning_nasdaq_figure(nasdaq, score, events)
    assert len(fig.data) >= 2


class MixedTzMarketData:
    """Simulates yfinance returning tz-aware indices for some tickers."""

    def get_history(self, symbol: str, start: str, end: str, interval: str = "1d") -> pd.DataFrame:
        idx = pd.date_range("2020-01-01", periods=120, freq="B")
        if symbol.startswith("^"):
            idx = idx.tz_localize("America/New_York")
        return pd.DataFrame({"Close": [100 + i * 0.1 for i in range(120)]}, index=idx)


def test_download_panel_handles_mixed_timezones() -> None:
    panel = _download_panel(MixedTzMarketData(), "2020-01-01", "2020-06-01")
    assert not panel.empty
    assert panel.index.tz is None
