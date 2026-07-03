from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from stock_trader.crash_warning import (
    CRASH_ALERT_THRESHOLD,
    PREDICTIVE_SIGNAL_RULES,
    _signal_active,
)

CRASH_DRAWDOWN = 0.15
FORWARD_HORIZON_DAYS = 126


@dataclass(frozen=True)
class ConfluenceRule:
    """Historically calibrated rule: when active, P(NASDAQ 15%+ DD in 6mo) ≈ probability."""

    name: str
    probability: float
    sample_size: int
    check: Callable[[dict[str, bool]], bool]


def _active_flags(row: pd.Series) -> dict[str, bool]:
    return {rule.key: _signal_active(rule.key, row) for rule in PREDICTIVE_SIGNAL_RULES}


# Ordered highest-probability first (1994–2026 NASDAQ backtest, 6-month 15%+ drawdown).
CONFLUENCE_RULES: tuple[ConfluenceRule, ...] = (
    ConfluenceRule(
        "VIX surge + SPY momentum + NASDAQ lag",
        1.00,
        41,
        lambda a: a["vix_rising"] and a["momentum_12_1"] and a["ixic_lag"],
    ),
    ConfluenceRule(
        "VIX surge + NASDAQ momentum + NASDAQ lag",
        1.00,
        42,
        lambda a: a["vix_rising"] and a["ixic_momentum_12_1"] and a["ixic_lag"],
    ),
    ConfluenceRule(
        "Credit stress + VIX surge + dual momentum",
        0.93,
        29,
        lambda a: a["credit_stress"]
        and a["vix_rising"]
        and a["momentum_12_1"]
        and a["ixic_momentum_12_1"],
    ),
    ConfluenceRule(
        "VIX−RVOL spread + dual momentum + NASDAQ lag",
        0.895,
        19,
        lambda a: a["vix_rvol_spread"]
        and a["momentum_12_1"]
        and a["ixic_momentum_12_1"]
        and a["ixic_lag"],
    ),
    ConfluenceRule(
        "VIX stress + momentum + NASDAQ lag",
        0.879,
        58,
        lambda a: (a["vix_rising"] or a["vix_rvol_spread"])
        and (a["momentum_12_1"] or a["ixic_momentum_12_1"])
        and a["ixic_lag"],
    ),
    ConfluenceRule(
        "Yield curve inverted + VIX surge + NASDAQ lag",
        0.846,
        13,
        lambda a: a["yc_inverted"] and a["vix_rising"] and a["ixic_lag"],
    ),
    ConfluenceRule(
        "VIX surge + NASDAQ weakness cluster",
        0.836,
        67,
        lambda a: a["vix_rising"]
        and a["ixic_lag"]
        and (a["momentum_12_1"] or a["ixic_momentum_12_1"] or a["smallcap_lag"]),
    ),
    ConfluenceRule(
        "Yield curve inverted + VIX−RVOL spread",
        0.80,
        20,
        lambda a: a["yc_inverted"] and a["vix_rvol_spread"],
    ),
    ConfluenceRule(
        "VIX surge + dual momentum",
        0.774,
        124,
        lambda a: a["vix_rising"] and a["momentum_12_1"] and a["ixic_momentum_12_1"],
    ),
    ConfluenceRule(
        "SPY + NASDAQ momentum + NASDAQ lag",
        0.749,
        342,
        lambda a: a["momentum_12_1"] and a["ixic_momentum_12_1"] and a["ixic_lag"],
    ),
    ConfluenceRule(
        "SPY momentum + NASDAQ lag",
        0.742,
        349,
        lambda a: a["momentum_12_1"] and a["ixic_lag"],
    ),
    ConfluenceRule(
        "VIX surge + NASDAQ lag",
        0.780,
        109,
        lambda a: a["vix_rising"] and a["ixic_lag"],
    ),
    ConfluenceRule(
        "NASDAQ 3-month loss > 10%",
        0.656,
        855,
        lambda a: a.get("_ixic_mom_63_lt_10", False),
    ),
    ConfluenceRule(
        "NASDAQ lagging SPY",
        0.497,
        969,
        lambda a: a["ixic_lag"],
    ),
    ConfluenceRule(
        "Baseline (no pattern matched)",
        0.286,
        8164,
        lambda a: True,
    ),
)


@dataclass(frozen=True)
class CrashProbabilityAssessment:
    probability: float
    rule_name: str
    sample_size: int
    high_confidence: bool
    active_flags: dict[str, bool]


def evaluate_crash_probability(row: pd.Series) -> CrashProbabilityAssessment:
    """Return calibrated 6-month NASDAQ crash probability for *row*."""
    flags = _active_flags(row)
    mom_63 = row.get("ixic_mom_63")
    flags["_ixic_mom_63_lt_10"] = bool(pd.notna(mom_63) and mom_63 < -0.10)

    for rule in CONFLUENCE_RULES:
        if rule.check(flags):
            return CrashProbabilityAssessment(
                probability=rule.probability,
                rule_name=rule.name,
                sample_size=rule.sample_size,
                high_confidence=rule.probability >= CRASH_ALERT_THRESHOLD,
                active_flags=flags,
            )

    return CrashProbabilityAssessment(
        probability=CONFLUENCE_RULES[-1].probability,
        rule_name=CONFLUENCE_RULES[-1].name,
        sample_size=CONFLUENCE_RULES[-1].sample_size,
        high_confidence=False,
        active_flags=flags,
    )


def crash_probability_from_row(row: pd.Series) -> float:
    return evaluate_crash_probability(row).probability


def crash_probability_series(
    features: pd.DataFrame,
    *,
    monthly: bool = False,
    smooth: int = 0,
) -> pd.Series:
    """Historical crash probability (0–1) aligned to *features*."""
    if features.empty:
        return pd.Series(dtype=float)

    if monthly:
        points: dict[pd.Timestamp, float] = {}
        for _, group in features.groupby(features.index.to_period("M")):
            points[group.index[-1]] = crash_probability_from_row(group.iloc[-1])
        series = pd.Series(points).sort_index()
    else:
        probs = [crash_probability_from_row(features.iloc[i]) for i in range(len(features))]
        series = pd.Series(probs, index=features.index)

    if smooth > 1 and not series.empty:
        return series.rolling(smooth, min_periods=1).mean()
    return series


def crash_probability_chart(features: pd.DataFrame) -> pd.Series:
    """Quarterly crash probability with 2-quarter smoothing for charts."""
    if features.empty:
        return pd.Series(dtype=float)

    points: dict[pd.Timestamp, float] = {}
    for _, group in features.groupby(features.index.to_period("Q")):
        points[group.index[-1]] = crash_probability_from_row(group.iloc[0])
    series = pd.Series(points).sort_index()
    if len(series) >= 2:
        series = series.rolling(2, min_periods=1).mean()
    return series * 100.0
