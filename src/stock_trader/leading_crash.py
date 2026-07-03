from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from stock_trader.crash_warning import (
    CRASH_ALERT_THRESHOLD,
    PREDICTIVE_SIGNAL_RULES,
    _signal_active,
)

LEADING_HORIZON_MONTHS = 12
LEADING_DRAWDOWN_LIMIT = -0.08
LEADING_VIX_RISE_LIMIT = 0.30
LEADING_BASELINE = 0.286


@dataclass(frozen=True)
class LeadingRule:
    name: str
    probability: float
    sample_size: int
    check: Callable[[pd.Series], bool]


def _credit_worsening(row: pd.Series) -> bool:
    if not bool(row.get("credit_available", False)):
        return False
    val = row.get("credit_worsening")
    return bool(pd.notna(val) and val > 0.01)


def _credit_available(row: pd.Series) -> bool:
    return bool(row.get("credit_available", False))


# Rules that do not require credit ETF data (used before ~2007).
LEADING_RULES_NO_CREDIT: tuple[LeadingRule, ...] = (
    LeadingRule(
        "Small-cap weakness (breadth warning)",
        0.883,
        222,
        lambda r: _smallcap_lag(r),
    ),
    LeadingRule(
        "Yield curve inverted + small-cap weakness",
        0.788,
        52,
        lambda r: _yc_inverted(r) and _smallcap_lag(r),
    ),
    LeadingRule(
        "Yield curve inverted (macro)",
        0.745,
        271,
        lambda r: _yc_inverted(r),
    ),
    LeadingRule(
        "No leading pattern",
        LEADING_BASELINE,
        8164,
        lambda r: True,
    ),
)


def _rules_for_row(row: pd.Series) -> tuple[LeadingRule, ...]:
    if _credit_available(row):
        return LEADING_RULES
    return LEADING_RULES_NO_CREDIT


def _evaluate_rules(row: pd.Series, rules: tuple[LeadingRule, ...]) -> LeadingCrashAssessment:
    for rule in rules:
        if rule.check(row):
            return LeadingCrashAssessment(
                probability=rule.probability,
                rule_name=rule.name,
                sample_size=rule.sample_size,
                leading_eligible=True,
                high_confidence=rule.probability >= CRASH_ALERT_THRESHOLD,
            )
    return LeadingCrashAssessment(
        probability=LEADING_BASELINE,
        rule_name="No leading pattern",
        sample_size=8164,
        leading_eligible=True,
        high_confidence=False,
    )


def _smallcap_lag(row: pd.Series) -> bool:
    return _signal_active("smallcap_lag", row)


def _credit_stress(row: pd.Series) -> bool:
    return _signal_active("credit_stress", row)


def _yc_inverted(row: pd.Series) -> bool:
    return _signal_active("yc_inverted", row)


# Calibrated on leading-eligible days only (not in selloff, VIX not spiking).
# Target: NASDAQ 15%+ drawdown within 12 months (1994–2026 backtest).
LEADING_RULES: tuple[LeadingRule, ...] = (
    LeadingRule(
        "Credit stress + small-cap weakness",
        0.942,
        104,
        lambda r: _credit_stress(r) and _smallcap_lag(r),
    ),
    LeadingRule(
        "Credit stress + small-cap + credit worsening",
        0.898,
        49,
        lambda r: _credit_stress(r) and _smallcap_lag(r) and _credit_worsening(r),
    ),
    LeadingRule(
        "Small-cap weakness + credit worsening",
        0.874,
        95,
        lambda r: _smallcap_lag(r) and _credit_worsening(r),
    ),
    LeadingRule(
        "Small-cap weakness (breadth warning)",
        0.883,
        222,
        lambda r: _smallcap_lag(r),
    ),
    LeadingRule(
        "Yield curve inverted + small-cap weakness",
        0.788,
        52,
        lambda r: _yc_inverted(r) and _smallcap_lag(r),
    ),
    LeadingRule(
        "Yield curve inverted (macro)",
        0.745,
        271,
        lambda r: _yc_inverted(r),
    ),
    LeadingRule(
        "Credit stress (spread widening)",
        0.529,
        737,
        lambda r: _credit_stress(r),
    ),
    LeadingRule(
        "No leading pattern",
        LEADING_BASELINE,
        8164,
        lambda r: True,
    ),
)


@dataclass(frozen=True)
class LeadingCrashAssessment:
    probability: float
    rule_name: str
    sample_size: int
    leading_eligible: bool
    high_confidence: bool
    horizon_months: int = LEADING_HORIZON_MONTHS


def is_leading_eligible(row: pd.Series) -> bool:
    """True when the market is not already in a selloff (leading phase only)."""
    ixic_dd = row.get("ixic_dd")
    spy_dd = row.get("spy_dd")
    vix_rising = row.get("vix_rising")
    if pd.isna(ixic_dd) or pd.isna(spy_dd):
        return False
    if ixic_dd <= LEADING_DRAWDOWN_LIMIT or spy_dd <= LEADING_DRAWDOWN_LIMIT:
        return False
    if pd.notna(vix_rising) and vix_rising > LEADING_VIX_RISE_LIMIT:
        return False
    return True


def evaluate_leading_crash_probability(row: pd.Series) -> LeadingCrashAssessment:
    """12-month NASDAQ crash probability from leading indicators only."""
    rules = _rules_for_row(row)
    if not is_leading_eligible(row):
        suffix = " (small-cap/yield proxy)" if not _credit_available(row) else ""
        return LeadingCrashAssessment(
            probability=LEADING_BASELINE,
            rule_name=f"Leading inactive (selloff underway){suffix}",
            sample_size=0,
            leading_eligible=False,
            high_confidence=False,
        )

    assessment = _evaluate_rules(row, rules)
    if not _credit_available(row) and assessment.rule_name != "No leading pattern":
        assessment = LeadingCrashAssessment(
            probability=assessment.probability,
            rule_name=f"{assessment.rule_name} [no credit data]",
            sample_size=assessment.sample_size,
            leading_eligible=assessment.leading_eligible,
            high_confidence=assessment.high_confidence,
        )
    return assessment


def evaluate_leading_crash_probability_chart(row: pd.Series) -> LeadingCrashAssessment:
    """Chart display: when credit ETFs unavailable, use small-cap/yield rules even in selloffs."""
    rules = _rules_for_row(row)
    if _credit_available(row):
        if not is_leading_eligible(row):
            return LeadingCrashAssessment(
                probability=LEADING_BASELINE,
                rule_name="Leading inactive (selloff underway)",
                sample_size=0,
                leading_eligible=False,
                high_confidence=False,
            )
        return _evaluate_rules(row, rules)

    # Pre-~2007: credit unavailable — chart uses small-cap / yield curve proxy.
    assessment = _evaluate_rules(row, rules)
    return LeadingCrashAssessment(
        probability=assessment.probability,
        rule_name=f"{assessment.rule_name} [small-cap proxy]",
        sample_size=assessment.sample_size,
        leading_eligible=is_leading_eligible(row),
        high_confidence=assessment.probability >= CRASH_ALERT_THRESHOLD and is_leading_eligible(row),
    )


def leading_crash_probability_from_row(row: pd.Series) -> float:
    return evaluate_leading_crash_probability(row).probability


def leading_crash_probability_series(
    features: pd.DataFrame,
    *,
    monthly: bool = False,
    smooth: int = 0,
) -> pd.Series:
    if features.empty:
        return pd.Series(dtype=float)

    if monthly:
        points: dict[pd.Timestamp, float] = {}
        for _, group in features.groupby(features.index.to_period("M")):
            points[group.index[-1]] = leading_crash_probability_from_row(group.iloc[-1])
        series = pd.Series(points).sort_index()
    else:
        probs = [leading_crash_probability_from_row(features.iloc[i]) for i in range(len(features))]
        series = pd.Series(probs, index=features.index)

    if smooth > 1 and not series.empty:
        return series.rolling(smooth, min_periods=1).mean()
    return series


def leading_crash_probability_chart(features: pd.DataFrame) -> pd.Series:
    """Quarterly leading probability (0–100) with 2-quarter smoothing."""
    if features.empty:
        return pd.Series(dtype=float)

    points: dict[pd.Timestamp, float] = {}
    for _, group in features.groupby(features.index.to_period("Q")):
        row = group.iloc[0]
        points[group.index[-1]] = evaluate_leading_crash_probability_chart(row).probability
    series = pd.Series(points).sort_index()
    if len(series) >= 2:
        series = series.rolling(2, min_periods=1).mean()
    return series * 100.0


def leading_crash_guide_snippet() -> str:
    signal_lines = "\n".join(
        f"- **{r.label}** — leading {r.tier.value} signal"
        for r in PREDICTIVE_SIGNAL_RULES
        if r.key in {"yc_inverted", "yc_deteriorating", "credit_stress", "smallcap_lag"}
    )
    return f"""
### Leading crash probability (12-month)

Uses **macro and market precursors only** — no VIX spikes, momentum breaks, or
NASDAQ lag that fire during selloffs. Alerts are **suppressed** once NASDAQ/SPY
is already down 8%+ or VIX is surging.

**Leading signals:**
{signal_lines}

**≥80% alert examples (backtested):**
- Credit stress + small-cap weakness → **94%** (12mo)
- Small-cap weakness alone → **88%** (12mo)

**Validation:** 222 leading-eligible alert-days at ≥80%, **88%** actually crashed within 12 months.
"""


def crash_components_guide_markdown() -> str:
    """Plain-language guide for each crash score component (UI button)."""
    return """
### Score components explained

The **12-month leading crash probability** matches today's signal pattern to
historically calibrated rules. Only **leading** inputs count — nothing that
fires after a selloff is already underway.

---

#### Credit stress

**What it is:** Bond investors prefer safety over risk. Investment-grade bonds
(**LQD**) are outperforming high-yield / junk bonds (**HYG**) over the **past
3 months**.

**Formula:** `LQD 3mo return − HYG 3mo return`

**Signal ON when:** result **> 0** (safer credit beating risky credit).

**Why it leads:** Credit markets often weaken **before** stocks. When lenders
pull back from junk debt, equities can follow weeks or months later.

**Data:** HYG and LQD ETFs (reliable from ~2007). Before that, the **chart uses
small-cap and yield-curve signals only** as a proxy.

---

#### Small-cap weakness

**What it is:** Small companies are lagging large caps — market **breadth** is
narrowing even if headline indices still look fine.

**Tickers:** **IWM** (Russell 2000) vs **SPY** (S&P 500)

**Formula:** `IWM 3mo return − SPY 3mo return`

**Signal ON when:** IWM trails SPY by **more than 5%** over 3 months.

**Why it leads:** Small caps are sensitive to funding and recession fears.
They often roll over before NASDAQ / large-cap peaks.

---

#### Credit worsening

**What it is:** Credit stress is **accelerating** — the LQD-vs-HYG gap is
widening faster than it was 3 weeks ago.

**Formula:** change in `credit_stress` over **21 days**

**Signal ON when:** credit stress measure rose by **> 1%** over 21 days.

**Used in:** higher-confidence combos with credit stress and/or small-cap
weakness (e.g. both + worsening → ~87–90% historical 12mo crash rate).

---

#### Yield curve inverted

**What it is:** Short-term rates are above long-term rates — a classic
**recession warning**.

**Tickers:** **^TNX** (10-year Treasury yield) vs **^IRX** (3-month T-bill)

**Signal ON when:** 10Y yield **below** 3-month yield (spread < 0).

**Typical lead:** **6–18 months** before recessions and major equity drawdowns.

---

#### Yield curve flattening

**What it is:** The yield curve is **steepening toward inversion** — not
inverted yet, but moving that way.

**Signal ON when:** 10Y–3M spread fell by **> 0.75 percentage points** over
**6 months**.

**Typical lead:** Often precedes full inversion by several months.

---

#### Leading score suppression

The probability is **frozen / reduced** when the market is already in trouble:

- NASDAQ or SPY down **more than 8%** from peak, **or**
- VIX up **30%+** over 21 days

Then you see *"Leading score inactive"* — use **Live stress** rows instead.

---

#### Live stress (shown separately — **not** in the score)

| Component | Meaning |
|-----------|---------|
| **VIX elevated** | Fear gauge unusually high vs past year |
| **Below 200-day SMA** | SPY trend already broken |
| **Drawdown > 10%** | Selloff underway |
| **Realized vol spike** | Daily volatility already extreme |

These are **coincident** — useful to see *during* a crash, not for leading alerts.

---

#### How components combine → probability

| Pattern (leading-eligible days) | Historical 12mo crash rate |
|----------------------------------|----------------------------|
| Credit stress + small-cap weakness | **~94%** |
| Small-cap weakness alone | **~88%** |
| Yield curve inverted + small-cap weakness | **~79%** |
| Yield curve inverted alone | **~75%** |
| Credit stress alone | **~53%** |
| No pattern matched | **~29%** (baseline) |

**≥ 80%** → critical leading alert. Chart red line = 80% threshold.
"""
