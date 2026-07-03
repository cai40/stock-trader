from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd

from stock_trader.market_data import MarketDataProvider, YFinanceMarketData

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


class RiskLevel(str, Enum):
    RISK_ON = "risk_on"
    CAUTION = "caution"
    DEFENSIVE = "defensive"
    CRITICAL = "critical"


class SignalTier(str, Enum):
    MACRO = "macro"
    MARKET = "market"
    COINCIDENT = "coincident"


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


SIGNAL_RULES: tuple[SignalRule, ...] = (
    SignalRule(
        "yc_inverted",
        "Yield curve inverted",
        SignalTier.MACRO,
        "10Y yield below 3-month T-bill — recession precursor (12–18 month lead).",
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
        "Implied fear exceeds realized volatility by 10+ points — pre-crash stress.",
    ),
    SignalRule(
        "vix_elevated",
        "VIX elevated",
        SignalTier.MARKET,
        "VIX z-score above 1.5 vs its 1-year average.",
    ),
    SignalRule(
        "momentum_12_1",
        "12−1 momentum negative",
        SignalTier.MARKET,
        "12-month return minus 1-month return below zero — momentum deterioration.",
    ),
    SignalRule(
        "below_sma200",
        "Below 200-day SMA",
        SignalTier.COINCIDENT,
        "SPY price below its 200-day moving average — trend break.",
    ),
    SignalRule(
        "drawdown_10",
        "Drawdown > 10%",
        SignalTier.COINCIDENT,
        "SPY is more than 10% below its 252-day high.",
    ),
    SignalRule(
        "vol_spike",
        "Realized vol spike",
        SignalTier.COINCIDENT,
        "20-day annualized volatility above 25%.",
    ),
)


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
    coincident_count: int
    fake_panic: bool
    fake_panic_reason: str
    action: str
    signals: list[SignalStatus] = field(default_factory=list)
    composite_score: float = 0.0


def _download_panel(
    market_data: MarketDataProvider,
    start: str,
    end: str,
) -> pd.DataFrame:
    frames: dict[str, pd.Series] = {}
    for name, ticker in PANEL_SYMBOLS.items():
        history = market_data.get_history(ticker, start=start, end=end)
        frames[name] = history["Close"].astype(float)
    panel = pd.DataFrame(frames).sort_index().ffill()
    return panel.dropna(how="all")


def compute_crash_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Build backward-looking crash indicator features from a multi-asset panel."""
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

    if "TNX" in panel and "IRX" in panel:
        feat["yc_slope"] = panel["TNX"] - panel["IRX"]
        feat["yc_inverted"] = (feat["yc_slope"] < 0).astype(int)

    if "HYG" in panel and "LQD" in panel:
        feat["credit_stress"] = (
            panel["LQD"].pct_change(CREDIT_WINDOW) - panel["HYG"].pct_change(CREDIT_WINDOW)
        )

    if "IWM" in panel:
        feat["smallcap_lag"] = panel["IWM"].pct_change(SMALLCAP_LAG_WINDOW) - spy.pct_change(
            SMALLCAP_LAG_WINDOW
        )

    if "IXIC" in panel:
        feat["nasdaq_lag"] = panel["IXIC"].pct_change(SMALLCAP_LAG_WINDOW) - spy.pct_change(
            SMALLCAP_LAG_WINDOW
        )

    return feat


def _signal_active(key: str, row: pd.Series) -> bool:
    if key == "yc_inverted":
        return bool(row.get("yc_inverted", 0) == 1)
    if key == "credit_stress":
        return bool(row.get("credit_stress", 0) > 0)
    if key == "smallcap_lag":
        val = row.get("smallcap_lag")
        return bool(pd.notna(val) and val < -0.05)
    if key == "vix_rvol_spread":
        val = row.get("vix_rvol_spread")
        return bool(pd.notna(val) and val > 10)
    if key == "vix_elevated":
        val = row.get("vix_zscore")
        return bool(pd.notna(val) and val > 1.5)
    if key == "momentum_12_1":
        val = row.get("momentum_12_1")
        return bool(pd.notna(val) and val < 0)
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
        "credit_stress": ("credit_stress", lambda v: f"{v * 100:.2f}%"),
        "smallcap_lag": ("smallcap_lag", lambda v: f"{v * 100:.2f}%"),
        "vix_rvol_spread": ("vix_rvol_spread", lambda v: f"{v:.1f}"),
        "vix_elevated": ("vix_zscore", lambda v: f"{v:.2f}"),
        "momentum_12_1": ("momentum_12_1", lambda v: f"{v * 100:.2f}%"),
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


def _detect_fake_panic(row: pd.Series, signals: list[SignalStatus]) -> tuple[bool, str]:
    """VIX spike without credit confirmation — often a headline panic, not systemic."""
    vix_on = any(s.rule.key == "vix_elevated" and s.active for s in signals)
    vix_rvol_on = any(s.rule.key == "vix_rvol_spread" and s.active for s in signals)
    credit_on = any(s.rule.key == "credit_stress" and s.active for s in signals)
    below_trend = bool(row.get("below_sma200", 0) == 1)

    if (vix_on or vix_rvol_on) and not credit_on and not below_trend:
        return True, (
            "VIX is elevated but credit markets are calm and SPY remains above its "
            "200-day average — possible headline panic rather than systemic stress."
        )
    return False, ""


def _risk_level_from_counts(macro: int, market: int, coincident: int) -> RiskLevel:
    total = macro + market + coincident
    if coincident >= 2 or total >= 5:
        return RiskLevel.CRITICAL
    if total >= 4 or macro >= 1 and market >= 2:
        return RiskLevel.DEFENSIVE
    if total >= 2:
        return RiskLevel.CAUTION
    return RiskLevel.RISK_ON


def assess_crash_risk(features: pd.DataFrame) -> CrashAssessment:
    """Evaluate crash early-warning signals on the last row of *features*."""
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

    macro = sum(1 for s in signals if s.active and s.rule.tier is SignalTier.MACRO)
    market = sum(1 for s in signals if s.active and s.rule.tier is SignalTier.MARKET)
    coincident = sum(1 for s in signals if s.active and s.rule.tier is SignalTier.COINCIDENT)
    fake_panic, fake_reason = _detect_fake_panic(row, signals)

    level = _risk_level_from_counts(macro, market, coincident)
    if fake_panic and level in {RiskLevel.DEFENSIVE, RiskLevel.CRITICAL}:
        level = RiskLevel.CAUTION

    composite = macro * 2.0 + market * 1.5 + coincident * 1.0

    return CrashAssessment(
        as_of=as_of,
        risk_level=level,
        active_count=macro + market + coincident,
        macro_count=macro,
        market_count=market,
        coincident_count=coincident,
        fake_panic=fake_panic,
        fake_panic_reason=fake_reason,
        action=RISK_ACTIONS[level],
        signals=signals,
        composite_score=composite,
    )


def composite_score_series(features: pd.DataFrame) -> pd.Series:
    """Historical composite warning score for charting."""
    scores: list[float] = []
    for i in range(len(features)):
        row = features.iloc[i]
        macro = market = coincident = 0
        for rule in SIGNAL_RULES:
            if not _signal_active(rule.key, row):
                continue
            if rule.tier is SignalTier.MACRO:
                macro += 1
            elif rule.tier is SignalTier.MARKET:
                market += 1
            else:
                coincident += 1
        scores.append(macro * 2.0 + market * 1.5 + coincident * 1.0)
    return pd.Series(scores, index=features.index)


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
