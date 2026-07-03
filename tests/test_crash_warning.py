from __future__ import annotations

import pandas as pd
import pytest

from stock_trader.crash_backtest import run_crash_score_backtest
from stock_trader.crash_warning import (
    CRASH_ALERT_THRESHOLD,
    HISTORICAL_CRASHES,
    RiskLevel,
    SignalTier,
    _download_panel,
    assess_crash_risk,
    compute_crash_features,
    crash_score_guide_markdown,
    crashes_in_range,
    load_crash_panel,
    nasdaq_normalized,
)
from stock_trader.leading_crash import (
    crash_components_guide_markdown,
    evaluate_leading_crash_probability,
    is_leading_eligible,
    leading_crash_probability_chart,
    leading_crash_probability_series,
)
from stock_trader.charts import (
    CRASH_LABEL_SHORT,
    crash_chart_data_range,
    crash_chart_zoom_range,
    crash_warning_nasdaq_figure,
)


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
    assert "ixic_dd" in features.columns
    assert "spy_dd" in features.columns
    assert "credit_worsening" in features.columns


def test_assess_crash_risk_risk_on_in_calm_market() -> None:
    features = compute_crash_features(_rising_panel()).dropna()
    assessment = assess_crash_risk(features)
    assert assessment.risk_level is RiskLevel.RISK_ON
    assert assessment.leading_eligible
    assert assessment.crash_probability < CRASH_ALERT_THRESHOLD


def test_stress_panel_suppresses_leading_score() -> None:
    features = compute_crash_features(_stress_panel()).dropna()
    assessment = assess_crash_risk(features)
    assert not assessment.leading_eligible
    assert assessment.stress_score >= 1


def test_predictive_score_excludes_coincident_tiers() -> None:
    features = compute_crash_features(_stress_panel()).dropna()
    assessment = assess_crash_risk(features)
    coincident = [s for s in assessment.signals if s.rule.tier is SignalTier.COINCIDENT and s.active]
    assert assessment.stress_score == float(len(coincident))


def test_leading_probability_series() -> None:
    features = compute_crash_features(_rising_panel()).dropna()
    scores = leading_crash_probability_series(features, monthly=True)
    assert len(scores) <= len(features)
    assert 0.0 <= float(scores.iloc[-1]) <= 1.0


def test_leading_crash_probability_chart() -> None:
    features = compute_crash_features(_rising_panel()).dropna()
    chart = leading_crash_probability_chart(features)
    assert len(chart) < len(features)
    assert chart.max() <= 100.0


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


def test_crashes_in_range_includes_partial_overlap() -> None:
    events = crashes_in_range(pd.Timestamp("2009-01-01"), pd.Timestamp("2012-01-01"))
    names = {e.name for e in events}
    assert "Global Financial Crisis" in names
    assert "2011 debt crisis" in names


def test_historical_crashes_include_2025_and_2026_march() -> None:
    names = {e.name for e in HISTORICAL_CRASHES}
    assert "2025 March selloff" in names
    assert "2026 March selloff" in names
    assert CRASH_LABEL_SHORT["2025 March selloff"] == "Mar'25"
    assert CRASH_LABEL_SHORT["2026 March selloff"] == "Mar'26"


def test_crashes_in_range_includes_2025_march() -> None:
    events = crashes_in_range(pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31"))
    names = {e.name for e in events}
    assert "2025 March selloff" in names


def test_crash_chart_zoom_range() -> None:
    full_start = pd.Timestamp("2020-01-01")
    full_end = pd.Timestamp("2025-01-01")
    current = (pd.Timestamp("2022-01-01"), pd.Timestamp("2024-01-01"))
    zoomed_in = crash_chart_zoom_range(full_start, full_end, current, factor=0.5)
    assert zoomed_in[1] - zoomed_in[0] < current[1] - current[0]
    zoomed_out = crash_chart_zoom_range(full_start, full_end, current, factor=2.0)
    assert zoomed_out[1] - zoomed_out[0] > current[1] - current[0]


def test_crash_warning_nasdaq_figure_respects_x_range() -> None:
    panel = _rising_panel()
    features = compute_crash_features(panel).dropna()
    score = leading_crash_probability_chart(features)
    nasdaq = nasdaq_normalized(panel, panel.index[0])
    events = crashes_in_range(panel.index[0], panel.index[-1])
    x_range = (panel.index[50], panel.index[150])
    fig = crash_warning_nasdaq_figure(nasdaq, score, events, x_range=x_range)
    assert fig.layout.xaxis.range[0] == x_range[0]
    assert fig.layout.xaxis2.range[0] == x_range[0]
    assert fig.layout.yaxis.fixedrange is True
    assert fig.layout.yaxis2.fixedrange is True


def test_crash_warning_nasdaq_figure_marks_crashes_on_both_panels() -> None:
    panel = _rising_panel()
    features = compute_crash_features(panel).dropna()
    score = leading_crash_probability_chart(features)
    nasdaq = nasdaq_normalized(panel, panel.index[0])
    events = crashes_in_range(panel.index[0], panel.index[-1])
    fig = crash_warning_nasdaq_figure(nasdaq, score, events)
    assert len(fig.data) >= 2
    marker_traces = [t for t in fig.data if getattr(t, "mode", "") and "markers" in t.mode]
    assert len(marker_traces) >= len(events) * 2


class MixedTzMarketData:
    def get_history(self, symbol: str, start: str, end: str, interval: str = "1d") -> pd.DataFrame:
        idx = pd.date_range("2020-01-01", periods=120, freq="B")
        if symbol.startswith("^"):
            idx = idx.tz_localize("America/New_York")
        return pd.DataFrame({"Close": [100 + i * 0.1 for i in range(120)]}, index=idx)


def test_download_panel_handles_mixed_timezones() -> None:
    panel = _download_panel(MixedTzMarketData(), "2020-01-01", "2020-06-01")
    assert not panel.empty
    assert panel.index.tz is None


def test_crash_score_guide_mentions_leading() -> None:
    guide = crash_score_guide_markdown()
    assert "leading" in guide.lower()
    assert "80%" in guide


def test_crash_components_guide_covers_key_signals() -> None:
    guide = crash_components_guide_markdown()
    assert "Credit stress" in guide
    assert "Small-cap weakness" in guide
    assert "Yield curve inverted" in guide
    assert "Live stress" in guide
    assert "HYG" in guide and "IWM" in guide


def test_evaluate_leading_crash_probability_baseline() -> None:
    features = compute_crash_features(_rising_panel()).dropna()
    prob = evaluate_leading_crash_probability(features.iloc[-1])
    assert prob.leading_eligible
    assert prob.probability < CRASH_ALERT_THRESHOLD


def test_is_leading_eligible_false_in_drawdown() -> None:
    features = compute_crash_features(_stress_panel()).dropna()
    row = features.iloc[-1]
    assert not is_leading_eligible(row)


def test_credit_available_column() -> None:
    features = compute_crash_features(_rising_panel()).dropna()
    assert "credit_available" in features.columns


def test_chart_uses_smallcap_proxy_pre_credit() -> None:
    from stock_trader.leading_crash import evaluate_leading_crash_probability_chart

    panel = _stress_panel()
    features = compute_crash_features(panel).dropna()
    features["credit_available"] = False
    row = features.iloc[-1]
    chart_ev = evaluate_leading_crash_probability_chart(row)
    assert "proxy" in chart_ev.rule_name


def test_run_crash_score_backtest_on_synthetic_panel() -> None:
    panel = _rising_panel()
    features = compute_crash_features(panel).dropna()
    nasdaq = panel["IXIC"].reindex(features.index)
    result = run_crash_score_backtest(features, nasdaq)
    assert result.n_days == len(features)
    assert result.alert_threshold == CRASH_ALERT_THRESHOLD
