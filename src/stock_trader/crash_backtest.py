from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from stock_trader.crash_probability import (
    CRASH_ALERT_THRESHOLD,
    crash_probability_series,
)
from stock_trader.crash_warning import HISTORICAL_CRASHES

CRASH_DRAWDOWN = 0.15
FORWARD_3M = 63
FORWARD_6M = 126
FORWARD_12M = 252
EARLY_WARNING_DAYS = 365


def _roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    y_true = y_true.astype(int)
    if len(np.unique(y_true)) < 2:
        return float("nan")
    pos = y_score[y_true == 1]
    neg = y_score[y_true == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    ranks = pd.Series(y_score).rank(method="average").values
    rank_sum_pos = ranks[y_true == 1].sum()
    n1, n0 = len(pos), len(neg)
    return float((rank_sum_pos - n1 * (n1 + 1) / 2) / (n1 * n0))


def _forward_max_drawdown(price: pd.Series, window: int) -> pd.Series:
    out = pd.Series(index=price.index, dtype=float)
    values = price.values
    for i in range(len(values)):
        end = min(i + window, len(values))
        if end <= i + 1:
            out.iloc[i] = np.nan
            continue
        segment = values[i:end]
        peak = segment[0]
        max_dd = 0.0
        for px in segment:
            peak = max(peak, px)
            max_dd = min(max_dd, px / peak - 1)
        out.iloc[i] = max_dd
    return out


def _auc_for_horizon(
    scores: pd.Series,
    price: pd.Series,
    *,
    days: int,
) -> float:
    label = (_forward_max_drawdown(price, days) <= -CRASH_DRAWDOWN).astype(int)
    mask = label.notna() & scores.notna()
    if mask.sum() < 50:
        return float("nan")
    return _roc_auc(label[mask].values, scores[mask].values)


def _threshold_metrics(
    scores: pd.Series,
    crash_label: pd.Series,
    threshold: float,
) -> tuple[float, float, int, int]:
    pred = (scores >= threshold).astype(int)
    mask = crash_label.notna()
    tp = int(((pred == 1) & (crash_label == 1))[mask].sum())
    fp = int(((pred == 1) & (crash_label == 0))[mask].sum())
    fn = int(((pred == 0) & (crash_label == 1))[mask].sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return precision, recall, tp + fp, tp


@dataclass(frozen=True)
class EarlyWarningResult:
    name: str
    peak: str
    flagged: bool
    max_prob_prior: float
    prob_at_peak: float


@dataclass(frozen=True)
class CrashScoreBacktest:
    period_start: str
    period_end: str
    n_days: int
    auc_3m: float
    auc_6m: float
    auc_12m: float
    alert_threshold: float
    alert_precision_6m: float
    alert_recall_6m: float
    alert_days: int
    crash_prob_at_alert: float
    crash_prob_baseline: float
    calibration_error: float
    early_warning_hits: int
    early_warning_total: int
    early_warnings: list[EarlyWarningResult] = field(default_factory=list)


def run_crash_score_backtest(
    features: pd.DataFrame,
    nasdaq: pd.Series,
    *,
    alert_threshold: float = CRASH_ALERT_THRESHOLD,
) -> CrashScoreBacktest:
    """Validate crash probability against forward NASDAQ drawdowns."""
    if features.empty or nasdaq.empty:
        raise ValueError("features and nasdaq price series are required")

    ixic = nasdaq.reindex(features.index).ffill()
    daily_prob = crash_probability_series(features, monthly=False)
    crash_6m = (_forward_max_drawdown(ixic, FORWARD_6M) <= -CRASH_DRAWDOWN).astype(int)

    precision, recall, alerts, _ = _threshold_metrics(
        daily_prob, crash_6m, alert_threshold
    )

    alert_mask = daily_prob >= alert_threshold
    prob_at_alert = float(crash_6m[alert_mask].mean()) if alert_mask.any() else float("nan")
    prob_base = float(crash_6m.mean())

    # Mean absolute calibration error: |stated prob - actual rate| on alert days
    cal_error = float(abs(daily_prob[alert_mask].mean() - prob_at_alert)) if alert_mask.any() else 0.0

    early: list[EarlyWarningResult] = []
    hits = 0
    for event in HISTORICAL_CRASHES:
        peak = pd.Timestamp(event.peak)
        if peak < features.index[0] or peak > features.index[-1]:
            continue
        window = daily_prob.loc[peak - pd.Timedelta(days=EARLY_WARNING_DAYS) : peak]
        flagged = bool((window >= alert_threshold).any()) if len(window) else False
        hits += int(flagged)
        prior_max = float(window.max()) if len(window) else float("nan")
        at_peak = float(daily_prob.loc[:peak].iloc[-1]) if len(daily_prob.loc[:peak]) else float("nan")
        early.append(
            EarlyWarningResult(
                name=event.name,
                peak=event.peak,
                flagged=flagged,
                max_prob_prior=prior_max,
                prob_at_peak=at_peak,
            )
        )

    return CrashScoreBacktest(
        period_start=str(features.index[0].date()),
        period_end=str(features.index[-1].date()),
        n_days=len(features),
        auc_3m=_auc_for_horizon(daily_prob, ixic, days=FORWARD_3M),
        auc_6m=_auc_for_horizon(daily_prob, ixic, days=FORWARD_6M),
        auc_12m=_auc_for_horizon(daily_prob, ixic, days=FORWARD_12M),
        alert_threshold=alert_threshold,
        alert_precision_6m=precision,
        alert_recall_6m=recall,
        alert_days=alerts,
        crash_prob_at_alert=prob_at_alert,
        crash_prob_baseline=prob_base,
        calibration_error=cal_error,
        early_warning_hits=hits,
        early_warning_total=len(early),
        early_warnings=early,
    )


def backtest_summary_markdown(result: CrashScoreBacktest) -> str:
    """Human-readable backtest summary for the UI."""
    ew_lines = "\n".join(
        f"- **{e.name}**: {'✓ flagged' if e.flagged else '✗ missed'} "
        f"(max prior {e.max_prob_prior:.0%}, at peak {e.prob_at_peak:.0%})"
        for e in result.early_warnings
    )
    edge = result.crash_prob_at_alert - result.crash_prob_baseline
    return f"""
**Validation period:** {result.period_start} → {result.period_end} ({result.n_days:,} trading days)

**Forward prediction (NASDAQ 15%+ drawdown within 6 months):**

| Metric | Value |
|--------|-------|
| AUC 3mo / 6mo / 12mo | {result.auc_3m:.2f} / {result.auc_6m:.2f} / {result.auc_12m:.2f} |
| **At ≥{result.alert_threshold:.0%} alert** | **{result.crash_prob_at_alert:.1%}** actual crash rate |
| Baseline (all days) | {result.crash_prob_baseline:.1%} |
| Edge over baseline | **{edge:+.1%}** |
| Precision / recall | {result.alert_precision_6m:.0%} / {result.alert_recall_6m:.0%} |
| Alert days | {result.alert_days:,} |
| Calibration error on alerts | {result.calibration_error:.1%} |

**Early warning** (probability ≥ {result.alert_threshold:.0%} within 12 months before peak):
{result.early_warning_hits}/{result.early_warning_total} major episodes flagged

{ew_lines}

*When the dashboard shows ≥80%, it means that exact signal pattern historically
led to a 15%+ NASDAQ drawdown within 6 months at that rate.*
"""
