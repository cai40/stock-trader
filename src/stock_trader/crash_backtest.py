from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from stock_trader.crash_warning import (
    DEFENSIVE_SCORE_THRESHOLD,
    HISTORICAL_CRASHES,
    predictive_score_chart,
    predictive_score_series,
)

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


def _crash_probability_after_threshold(
    scores: pd.Series,
    price: pd.Series,
    threshold: float,
    *,
    forward_days: int = FORWARD_6M,
) -> tuple[float, float]:
    fwd_dd = _forward_max_drawdown(price, forward_days)
    crash_label = (fwd_dd <= -CRASH_DRAWDOWN).astype(float)

    high = crash_label[scores >= threshold].dropna()
    baseline = crash_label.dropna()
    prob_high = float(high.mean()) if len(high) else float("nan")
    prob_base = float(baseline.mean()) if len(baseline) else float("nan")
    return prob_high, prob_base


@dataclass(frozen=True)
class EarlyWarningResult:
    name: str
    peak: str
    flagged: bool
    max_score_prior: float
    score_at_peak: float


@dataclass(frozen=True)
class CrashScoreBacktest:
    period_start: str
    period_end: str
    n_days: int
    auc_3m: float
    auc_6m: float
    auc_12m: float
    defensive_threshold: float
    defensive_precision_6m: float
    defensive_recall_6m: float
    defensive_alerts: int
    crash_prob_at_defensive: float
    crash_prob_baseline: float
    mean_forward_6m_at_defensive: float
    mean_forward_6m_calm: float
    early_warning_hits: int
    early_warning_total: int
    early_warnings: list[EarlyWarningResult] = field(default_factory=list)


def run_crash_score_backtest(
    features: pd.DataFrame,
    nasdaq: pd.Series,
    *,
    defensive_threshold: float = DEFENSIVE_SCORE_THRESHOLD,
) -> CrashScoreBacktest:
    """Validate predictive crash score against forward NASDAQ drawdowns."""
    if features.empty or nasdaq.empty:
        raise ValueError("features and nasdaq price series are required")

    ixic = nasdaq.reindex(features.index).ffill()
    daily_scores = predictive_score_series(features, monthly=False)
    crash_6m = (_forward_max_drawdown(ixic, FORWARD_6M) <= -CRASH_DRAWDOWN).astype(int)

    precision, recall, alerts, _ = _threshold_metrics(
        daily_scores, crash_6m, defensive_threshold
    )
    prob_high, prob_base = _crash_probability_after_threshold(
        daily_scores, ixic, defensive_threshold
    )

    fwd_ret_6m = ixic.shift(-FORWARD_6M) / ixic - 1
    calm_threshold = max(2.0, defensive_threshold - 3.0)
    hi_ret = fwd_ret_6m[daily_scores >= defensive_threshold].dropna()
    calm_ret = fwd_ret_6m[daily_scores < calm_threshold].dropna()

    early: list[EarlyWarningResult] = []
    hits = 0
    for event in HISTORICAL_CRASHES:
        peak = pd.Timestamp(event.peak)
        if peak < features.index[0] or peak > features.index[-1]:
            continue
        window = daily_scores.loc[peak - pd.Timedelta(days=EARLY_WARNING_DAYS) : peak]
        flagged = bool((window >= defensive_threshold).any()) if len(window) else False
        hits += int(flagged)
        prior_max = float(window.max()) if len(window) else float("nan")
        at_peak = float(daily_scores.loc[:peak].iloc[-1]) if len(daily_scores.loc[:peak]) else float("nan")
        early.append(
            EarlyWarningResult(
                name=event.name,
                peak=event.peak,
                flagged=flagged,
                max_score_prior=prior_max,
                score_at_peak=at_peak,
            )
        )

    return CrashScoreBacktest(
        period_start=str(features.index[0].date()),
        period_end=str(features.index[-1].date()),
        n_days=len(features),
        auc_3m=_auc_for_horizon(daily_scores, ixic, days=FORWARD_3M),
        auc_6m=_auc_for_horizon(daily_scores, ixic, days=FORWARD_6M),
        auc_12m=_auc_for_horizon(daily_scores, ixic, days=FORWARD_12M),
        defensive_threshold=defensive_threshold,
        defensive_precision_6m=precision,
        defensive_recall_6m=recall,
        defensive_alerts=alerts,
        crash_prob_at_defensive=prob_high,
        crash_prob_baseline=prob_base,
        mean_forward_6m_at_defensive=float(hi_ret.mean() * 100) if len(hi_ret) else float("nan"),
        mean_forward_6m_calm=float(calm_ret.mean() * 100) if len(calm_ret) else float("nan"),
        early_warning_hits=hits,
        early_warning_total=len(early),
        early_warnings=early,
    )


def backtest_summary_markdown(result: CrashScoreBacktest) -> str:
    """Human-readable backtest summary for the UI."""
    ew_lines = "\n".join(
        f"- **{e.name}**: {'✓ flagged' if e.flagged else '✗ missed'} "
        f"(max prior score {e.max_score_prior:.1f}, at peak {e.score_at_peak:.1f})"
        for e in result.early_warnings
    )
    edge = result.crash_prob_at_defensive - result.crash_prob_baseline
    return f"""
**Validation period:** {result.period_start} → {result.period_end} ({result.n_days:,} trading days)

**Forward prediction (NASDAQ 15%+ drawdown):**

| Horizon | AUC (0.5 = random) |
|---------|-------------------|
| 3 months | **{result.auc_3m:.2f}** |
| 6 months | **{result.auc_6m:.2f}** |
| 12 months | **{result.auc_12m:.2f}** |

**At defensive threshold (score ≥ {result.defensive_threshold:.0f}):**

| Metric | Value |
|--------|-------|
| 6-month crash probability | **{result.crash_prob_at_defensive:.1%}** vs {result.crash_prob_baseline:.1%} baseline |
| Edge over baseline | **{edge:+.1%}** |
| Precision / recall (6mo) | {result.defensive_precision_6m:.0%} / {result.defensive_recall_6m:.0%} |
| Alert days | {result.defensive_alerts:,} |

**Early warning** (score ≥ {result.defensive_threshold:.0f} within 12 months before crash peak):
{result.early_warning_hits}/{result.early_warning_total} major episodes flagged

{ew_lines}

*AUC measures ranking quality for future crashes. Higher crash probability at elevated scores
means the score leads selloffs rather than only reflecting them.*
"""
