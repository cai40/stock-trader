from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd

from stock_trader.market_data import MarketDataProvider, YFinanceMarketData, _normalize_index

PANEL_SYMBOLS = {
    "SPY": "SPY",
    "IXIC": "^IXIC",
    "VIX": "^VIX",
    "TNX": "^TNX",
    "IRX": "^IRX",
    "HYG": "HYG",
    "LQD": "LQD",
    "IWM": "IWM",
}

DEFAULT_CRASH_HISTORY_START = "1993-01-01"

LOOKBACK_ZSCORE = 252
VOL_WINDOW = 20
MOMENTUM_LONG = 252
MOMENTUM_SHORT = 21
SMALLCAP_LAG_WINDOW = 63
CREDIT_WINDOW = 63
YC_DETERIORATION_WINDOW = 126
VIX_RISING_WINDOW = 21

DEFENSIVE_SCORE_THRESHOLD = 6.0
CRITICAL_SCORE_THRESHOLD = 9.0


class RiskLevel(str, Enum):
    RISK_ON = "risk_on"
    CAUTION = "caution"
    DEFENSIVE = "defensive"
    CRITICAL = "critical"


class SignalTier(str, Enum):
    MACRO = "macro"
    MARKET = "market"
    NASDAQ = "nasdaq"
    COINCIDENT = "coincident"


TIER_WEIGHTS: dict[SignalTier, float] = {
    SignalTier.MACRO: 3.0,
    SignalTier.MARKET: 2.0,
    SignalTier.NASDAQ: 2.5,
    SignalTier.COINCIDENT: 0.0,
}


RISK_LABELS: dict[RiskLevel, str] = {
    RiskLevel.RISK_ON: "Risk-on",
    RiskLevel.CAUTION: "Caution",
    RiskLevel.DEFENSIVE: "Defensive",
    RiskLevel.CRITICAL: "Critical",
}

RISK_ACTIONS: dict[RiskLevel, str] = {
    RiskLevel.RISK_ON: "Normal exposure; buy-and-hold or vol-target strategies are appropriate.",
    RiskLevel.CAUTION: "Reduce equity exposure 25–50%; favor dual momentum or defensive rotation.",
    RiskLevel.DEFENSIVE: "Rotate to SHY/TLT/IEF; activate crisis overlays (hybrid vol + crisis).",
    RiskLevel.CRITICAL: "Maximum defense; cash and long-duration Treasuries until signals clear.",
}

RISK_COLORS: dict[RiskLevel, str] = {
    RiskLevel.RISK_ON: "#4ade80",
    RiskLevel.CAUTION: "#facc15",
    RiskLevel.DEFENSIVE: "#fb923c",
    RiskLevel.CRITICAL: "#f87171",
}


def risk_level_color(level: RiskLevel) -> str:
    return RISK_COLORS[level]


def crash_score_guide_markdown() -> str:
    """Detailed explanation of the predictive crash score for the UI guide."""
    predictive_lines = "\n".join(
        f"- **{rule.label}** ({rule.tier.value}) — {rule.description}"
        for rule in PREDICTIVE_SIGNAL_RULES
    )
    coincident_lines = "\n".join(
        f"- **{rule.label}** — {rule.description}" for rule in COINCIDENT_SIGNAL_RULES
    )
    return f"""
### What is the crash score?

A **predictive** NASDAQ crash score (0–~21) built from **leading** macro, market, and
NASDAQ-specific signals. It deliberately **excludes** lagging indicators (drawdowns,
below-trend price) so the score rises **before** crashes rather than after they start.

Data sources: **SPY**, **NASDAQ (^IXIC)**, **VIX**, **Treasury yields** (^TNX / ^IRX),
**HYG** (high-yield credit), **LQD** (investment-grade credit), **IWM** (small caps).

---

### Predictive signals (9)

{predictive_lines}

**Tiers:**
- **Macro** — slow-moving recession precursors (yield curve)
- **Market** — medium-term stress (credit, VIX build-up, momentum)
- **NASDAQ** — tech/growth weakness specific to NASDAQ crashes

---

### Live stress (not in score)

These fire **during** selloffs and are shown separately — they do **not** increase the
predictive score:

{coincident_lines}

---

### How the number is calculated

| Tier | Points per active signal |
|------|--------------------------|
| Macro | **3.0** |
| Market | **2.0** |
| NASDAQ | **2.5** |

**Formula:** `score = (macro × 3) + (market × 2) + (nasdaq × 2.5)`

Maximum possible score ≈ **21** (all 9 predictive signals on).

The **header metric** uses today's reading. The **chart** uses a **quarterly**
score with **2-quarter smoothing** for mobile readability.

---

### Risk levels

| Level | Typical trigger | Suggested posture |
|-------|-----------------|-------------------|
| **Risk-on** | score < 4 | Normal exposure |
| **Caution** | 4–5 | Trim equity 25–50% |
| **Defensive** | 6–8 | Rotate to bonds/cash |
| **Critical** | ≥ 9 | Maximum defense |

Chart reference lines: **orange = 6** (defensive), **red = 9** (critical).

---

### Fake panic filter

If VIX is rising but **credit markets are calm** and SPY is **above its 200-day
average**, the dashboard may downgrade the risk level — headline fear without
systemic stress.

---

### Limitations

- No score predicts every crash; false alarms still happen
- Credit ETF data (HYG/LQD) only exists from ~2007 onward
- Backtest stats in the dashboard show historical accuracy — not a guarantee
- Educational research tool — **not financial advice**
"""


@dataclass(frozen=True)
class CrashEvent:
    name: str
    peak: str
    trough: str


HISTORICAL_CRASHES: tuple[CrashEvent, ...] = (
    CrashEvent("Dot-com bust", "2000-03-24", "2002-10-09"),
    CrashEvent("Global Financial Crisis", "2007-10-09", "2009-03-09"),
    CrashEvent("2011 debt crisis", "2011-04-29", "2011-10-03"),
    CrashEvent("2018 Q4 selloff", "2018-09-20", "2018-12-24"),
    CrashEvent("COVID crash", "2020-02-19", "2020-03-23"),
    CrashEvent("2022 bear market", "2022-01-03", "2022-10-12"),
)


@dataclass(frozen=True)
class SignalRule:
    key: str
    label: str
    tier: SignalTier
    description: str


PREDICTIVE_SIGNAL_RULES: tuple[SignalRule, ...] = (
    SignalRule(
        "yc_inverted",
        "Yield curve inverted",
        SignalTier.MACRO,
        "10Y yield below 3-month T-bill — recession precursor (12–18 month lead).",
    ),
    SignalRule(
        "yc_deteriorating",
        "Yield curve flattening",
        SignalTier.MACRO,
        "10Y–3M spread fell >0.75pp over 6 months — inversion approaching.",
    ),
    SignalRule(
        "credit_stress",
        "Credit stress",
        SignalTier.MARKET,
        "Investment-grade bonds (LQD) outperforming high-yield (HYG) over 3 months.",
    ),
    SignalRule(
        "smallcap_lag",
        "Small-cap weakness",
        SignalTier.MARKET,
        "Russell 2000 (IWM) trailing SPY by more than 5% over 3 months.",
    ),
    SignalRule(
        "vix_rvol_spread",
        "VIX − realized vol spread",
        SignalTier.MARKET,
        "Implied fear exceeds realized volatility by 10+ points — stress building.",
    ),
    SignalRule(
        "vix_rising",
        "VIX rising fast",
        SignalTier.MARKET,
        "VIX up 30%+ over 21 days — fear building before price breaks.",
    ),
    SignalRule(
        "momentum_12_1",
        "SPY 12−1 momentum negative",
        SignalTier.MARKET,
        "Broad-market 12-month minus 1-month return below zero.",
    ),
    SignalRule(
        "ixic_momentum_12_1",
        "NASDAQ 12−1 momentum negative",
        SignalTier.NASDAQ,
        "NASDAQ 12-month minus 1-month return below zero — growth deterioration.",
    ),
    SignalRule(
        "ixic_lag",
        "NASDAQ lagging SPY",
        SignalTier.NASDAQ,
        "NASDAQ trailing SPY by more than 5% over 3 months — tech weakness.",
    ),
)

COINCIDENT_SIGNAL_RULES: tuple[SignalRule, ...] = (
    SignalRule(
        "vix_elevated",
        "VIX elevated",
        SignalTier.COINCIDENT,
        "VIX z-score above 1.5 vs its 1-year average — live fear gauge.",
    ),
    SignalRule(
        "below_sma200",
        "Below 200-day SMA",
        SignalTier.COINCIDENT,
        "SPY price below its 200-day moving average — trend already broken.",
    ),
    SignalRule(
        "drawdown_10",
        "Drawdown > 10%",
        SignalTier.COINCIDENT,
        "SPY is more than 10% below its 252-day high — selloff underway.",
    ),
    SignalRule(
        "vol_spike",
        "Realized vol spike",
        SignalTier.COINCIDENT,
        "20-day annualized volatility above 25% — crash already in progress.",
    ),
)

SIGNAL_RULES: tuple[SignalRule, ...] = PREDICTIVE_SIGNAL_RULES + COINCIDENT_SIGNAL_RULES


@dataclass
class SignalStatus:
    rule: SignalRule
    active: bool
    value: float | None
    display_value: str


@dataclass
class CrashAssessment:
    as_of: pd.Timestamp
    risk_level: RiskLevel
    active_count: int
    macro_count: int
    market_count: int
    nasdaq_count: int
    coincident_count: int
    fake_panic: bool
    fake_panic_reason: str
    action: str
    signals: list[SignalStatus] = field(default_factory=list)
    composite_score: float = 0.0
    stress_score: float = 0.0


def _download_panel(
    market_data: MarketDataProvider,
    start: str,
    end: str,
) -> pd.DataFrame:
    frames: dict[str, pd.Series] = {}
    for name, ticker in PANEL_SYMBOLS.items():
        history = market_data.get_history(ticker, start=start, end=end)
        series = history["Close"].astype(float)
        series.index = _normalize_index(series.index)
        frames[name] = series
    panel = pd.DataFrame(frames).sort_index().ffill()
    return panel.dropna(how="all")


def compute_crash_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Build crash indicator features from a multi-asset panel."""
    if panel.empty or "SPY" not in panel.columns:
        return pd.DataFrame()

    spy = panel["SPY"]
    ret = spy.pct_change()
    feat = pd.DataFrame(index=panel.index)

    feat["ret_3m"] = spy.pct_change(63)
    feat["vol_20d"] = ret.rolling(VOL_WINDOW).std() * np.sqrt(252)
    feat["dd_from_peak_252"] = spy / spy.rolling(LOOKBACK_ZSCORE).max() - 1
    feat["below_sma200"] = (spy < spy.rolling(200).mean()).astype(int)
    feat["momentum_12_1"] = spy.pct_change(MOMENTUM_LONG) - spy.pct_change(MOMENTUM_SHORT)

    if "VIX" in panel:
        vix = panel["VIX"]
        feat["vix"] = vix
        vix_mean = vix.rolling(LOOKBACK_ZSCORE).mean()
        vix_std = vix.rolling(LOOKBACK_ZSCORE).std()
        feat["vix_zscore"] = (vix - vix_mean) / vix_std
        feat["vix_rvol_spread"] = vix - feat["vol_20d"] * 100
        feat["vix_rising"] = vix.pct_change(VIX_RISING_WINDOW)

    if "TNX" in panel and "IRX" in panel:
        feat["yc_slope"] = panel["TNX"] - panel["IRX"]
        feat["yc_inverted"] = (feat["yc_slope"] < 0).astype(int)
        feat["yc_deteriorating"] = feat["yc_slope"] - feat["yc_slope"].shift(YC_DETERIORATION_WINDOW)

    if "HYG" in panel and "LQD" in panel:
        feat["credit_stress"] = (
            panel["LQD"].pct_change(CREDIT_WINDOW) - panel["HYG"].pct_change(CREDIT_WINDOW)
        )

    if "IWM" in panel:
        feat["smallcap_lag"] = panel["IWM"].pct_change(SMALLCAP_LAG_WINDOW) - spy.pct_change(
            SMALLCAP_LAG_WINDOW
        )

    if "IXIC" in panel:
        ixic = panel["IXIC"]
        feat["ixic_momentum_12_1"] = ixic.pct_change(MOMENTUM_LONG) - ixic.pct_change(MOMENTUM_SHORT)
        feat["ixic_lag"] = ixic.pct_change(SMALLCAP_LAG_WINDOW) - spy.pct_change(
            SMALLCAP_LAG_WINDOW
        )

    return feat


def _signal_active(key: str, row: pd.Series) -> bool:
    if key == "yc_inverted":
        return bool(row.get("yc_inverted", 0) == 1)
    if key == "yc_deteriorating":
        val = row.get("yc_deteriorating")
        return bool(pd.notna(val) and val < -0.75)
    if key == "credit_stress":
        return bool(row.get("credit_stress", 0) > 0)
    if key == "smallcap_lag":
        val = row.get("smallcap_lag")
        return bool(pd.notna(val) and val < -0.05)
    if key == "vix_rvol_spread":
        val = row.get("vix_rvol_spread")
        return bool(pd.notna(val) and val > 10)
    if key == "vix_rising":
        val = row.get("vix_rising")
        return bool(pd.notna(val) and val > 0.30)
    if key == "momentum_12_1":
        val = row.get("momentum_12_1")
        return bool(pd.notna(val) and val < 0)
    if key == "ixic_momentum_12_1":
        val = row.get("ixic_momentum_12_1")
        return bool(pd.notna(val) and val < 0)
    if key == "ixic_lag":
        val = row.get("ixic_lag")
        return bool(pd.notna(val) and val < -0.05)
    if key == "vix_elevated":
        val = row.get("vix_zscore")
        return bool(pd.notna(val) and val > 1.5)
    if key == "below_sma200":
        return bool(row.get("below_sma200", 0) == 1)
    if key == "drawdown_10":
        val = row.get("dd_from_peak_252")
        return bool(pd.notna(val) and val < -0.10)
    if key == "vol_spike":
        val = row.get("vol_20d")
        return bool(pd.notna(val) and val > 0.25)
    return False


def _format_value(key: str, row: pd.Series) -> tuple[float | None, str]:
    mapping = {
        "yc_inverted": ("yc_slope", lambda v: f"{v:.2f}pp"),
        "yc_deteriorating": ("yc_deteriorating", lambda v: f"{v:.2f}pp"),
        "credit_stress": ("credit_stress", lambda v: f"{v * 100:.2f}%"),
        "smallcap_lag": ("smallcap_lag", lambda v: f"{v * 100:.2f}%"),
        "vix_rvol_spread": ("vix_rvol_spread", lambda v: f"{v:.1f}"),
        "vix_rising": ("vix_rising", lambda v: f"{v * 100:.0f}%"),
        "momentum_12_1": ("momentum_12_1", lambda v: f"{v * 100:.2f}%"),
        "ixic_momentum_12_1": ("ixic_momentum_12_1", lambda v: f"{v * 100:.2f}%"),
        "ixic_lag": ("ixic_lag", lambda v: f"{v * 100:.2f}%"),
        "vix_elevated": ("vix_zscore", lambda v: f"{v:.2f}"),
        "below_sma200": ("below_sma200", lambda v: "Yes" if v == 1 else "No"),
        "drawdown_10": ("dd_from_peak_252", lambda v: f"{v * 100:.1f}%"),
        "vol_spike": ("vol_20d", lambda v: f"{v * 100:.1f}%"),
    }
    col, fmt = mapping.get(key, (key, str))
    if col not in row.index:
        return None, "—"
    val = row[col]
    if pd.isna(val):
        return None, "—"
    if key == "below_sma200":
        return float(val), fmt(val)
    return float(val), fmt(val)


def _tier_counts(signals: list[SignalStatus]) -> tuple[int, int, int, int]:
    macro = sum(1 for s in signals if s.active and s.rule.tier is SignalTier.MACRO)
    market = sum(1 for s in signals if s.active and s.rule.tier is SignalTier.MARKET)
    nasdaq = sum(1 for s in signals if s.active and s.rule.tier is SignalTier.NASDAQ)
    coincident = sum(1 for s in signals if s.active and s.rule.tier is SignalTier.COINCIDENT)
    return macro, market, nasdaq, coincident


def _predictive_score(macro: int, market: int, nasdaq: int) -> float:
    return macro * TIER_WEIGHTS[SignalTier.MACRO] + market * TIER_WEIGHTS[SignalTier.MARKET] + nasdaq * TIER_WEIGHTS[SignalTier.NASDAQ]


def _stress_score(coincident: int) -> float:
    return coincident * 1.0


def _detect_fake_panic(row: pd.Series, signals: list[SignalStatus]) -> tuple[bool, str]:
    """VIX building without credit confirmation — often headline panic, not systemic."""
    vix_rising = any(s.rule.key == "vix_rising" and s.active for s in signals)
    vix_rvol_on = any(s.rule.key == "vix_rvol_spread" and s.active for s in signals)
    credit_on = any(s.rule.key == "credit_stress" and s.active for s in signals)
    below_trend = bool(row.get("below_sma200", 0) == 1)

    if (vix_rising or vix_rvol_on) and not credit_on and not below_trend:
        return True, (
            "VIX is rising but credit markets are calm and SPY remains above its "
            "200-day average — possible headline panic rather than systemic stress."
        )
    return False, ""


def _risk_level_from_score(score: float, macro: int, market: int, nasdaq: int) -> RiskLevel:
    if score >= CRITICAL_SCORE_THRESHOLD or (macro >= 1 and nasdaq >= 1 and market >= 2):
        return RiskLevel.CRITICAL
    if score >= DEFENSIVE_SCORE_THRESHOLD or (macro >= 1 and market >= 2):
        return RiskLevel.DEFENSIVE
    if score >= 4.0 or macro + market + nasdaq >= 2:
        return RiskLevel.CAUTION
    return RiskLevel.RISK_ON


def assess_crash_risk(features: pd.DataFrame) -> CrashAssessment:
    """Evaluate predictive crash signals on the last row of *features*."""
    if features.empty:
        raise ValueError("feature frame is empty")

    row = features.iloc[-1]
    as_of = features.index[-1]
    signals: list[SignalStatus] = []

    for rule in SIGNAL_RULES:
        value, display = _format_value(rule.key, row)
        signals.append(
            SignalStatus(
                rule=rule,
                active=_signal_active(rule.key, row),
                value=value,
                display_value=display,
            )
        )

    macro, market, nasdaq, coincident = _tier_counts(signals)
    fake_panic, fake_reason = _detect_fake_panic(row, signals)
    composite = _predictive_score(macro, market, nasdaq)
    stress = _stress_score(coincident)

    level = _risk_level_from_score(composite, macro, market, nasdaq)
    if fake_panic and level in {RiskLevel.DEFENSIVE, RiskLevel.CRITICAL}:
        level = RiskLevel.CAUTION

    predictive_active = macro + market + nasdaq

    return CrashAssessment(
        as_of=as_of,
        risk_level=level,
        active_count=predictive_active,
        macro_count=macro,
        market_count=market,
        nasdaq_count=nasdaq,
        coincident_count=coincident,
        fake_panic=fake_panic,
        fake_panic_reason=fake_reason,
        action=RISK_ACTIONS[level],
        signals=signals,
        composite_score=composite,
        stress_score=stress,
    )


def _score_from_row(row: pd.Series) -> float:
    macro = market = nasdaq = 0
    for rule in PREDICTIVE_SIGNAL_RULES:
        if not _signal_active(rule.key, row):
            continue
        if rule.tier is SignalTier.MACRO:
            macro += 1
        elif rule.tier is SignalTier.MARKET:
            market += 1
        else:
            nasdaq += 1
    return _predictive_score(macro, market, nasdaq)


def predictive_score_series(
    features: pd.DataFrame,
    *,
    monthly: bool = False,
    smooth: int = 0,
) -> pd.Series:
    """Daily or monthly predictive crash score history."""
    if features.empty:
        return pd.Series(dtype=float)

    if monthly:
        points: dict[pd.Timestamp, float] = {}
        for _, group in features.groupby(features.index.to_period("M")):
            points[group.index[-1]] = _score_from_row(group.iloc[-1])
        series = pd.Series(points).sort_index()
    else:
        scores = [_score_from_row(features.iloc[i]) for i in range(len(features))]
        series = pd.Series(scores, index=features.index)

    if smooth > 1 and not series.empty:
        return series.rolling(smooth, min_periods=1).mean()
    return series


def predictive_score_chart(features: pd.DataFrame) -> pd.Series:
    """Quarterly predictive score with 2-quarter smoothing for charts."""
    if features.empty:
        return pd.Series(dtype=float)

    points: dict[pd.Timestamp, float] = {}
    for _, group in features.groupby(features.index.to_period("Q")):
        score = _score_from_row(group.iloc[0])
        points[group.index[-1]] = score
    series = pd.Series(points).sort_index()
    if len(series) >= 2:
        series = series.rolling(2, min_periods=1).mean()
    return series


def composite_score_chart(features: pd.DataFrame) -> pd.Series:
    """Alias for :func:`predictive_score_chart` (backward compatible)."""
    return predictive_score_chart(features)


def composite_score_monthly(features: pd.DataFrame) -> pd.Series:
    """One predictive score per calendar month."""
    return predictive_score_series(features, monthly=True)


def composite_score_series(
    features: pd.DataFrame,
    *,
    monthly: bool = True,
    smooth: int = 0,
) -> pd.Series:
    """Historical predictive crash score."""
    return predictive_score_series(features, monthly=monthly, smooth=smooth)


def nasdaq_normalized(panel: pd.DataFrame, start: pd.Timestamp) -> pd.Series:
    """NASDAQ Composite indexed to 100 at *start* for overlay charts."""
    if "IXIC" not in panel.columns:
        return pd.Series(dtype=float)
    series = panel["IXIC"].astype(float).loc[panel.index >= start]
    if series.empty:
        return series
    base = float(series.iloc[0])
    if base <= 0:
        return series
    return series / base * 100.0


def crashes_in_range(start: pd.Timestamp, end: pd.Timestamp) -> list[CrashEvent]:
    """Return historical crash episodes overlapping [start, end]."""
    events: list[CrashEvent] = []
    for event in HISTORICAL_CRASHES:
        peak = pd.Timestamp(event.peak)
        trough = pd.Timestamp(event.trough)
        if trough >= start and peak <= end:
            events.append(event)
    return events


def load_crash_panel(
    start: str,
    end: str,
    market_data: MarketDataProvider | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, CrashAssessment]:
    """Download panel data, compute features, and return the latest assessment."""
    provider = market_data or YFinanceMarketData()
    warmup_start = (pd.Timestamp(start) - pd.Timedelta(days=LOOKBACK_ZSCORE + 60)).strftime(
        "%Y-%m-%d"
    )
    panel = _download_panel(provider, warmup_start, end)
    features = compute_crash_features(panel)
    features = features.loc[features.index >= pd.Timestamp(start)]
    core = [col for col in ("vol_20d", "dd_from_peak_252") if col in features.columns]
    if core:
        features = features.dropna(subset=core)
    if features.empty:
        raise ValueError("insufficient data to compute crash warning features")
    assessment = assess_crash_risk(features)
    return panel, features, assessment
