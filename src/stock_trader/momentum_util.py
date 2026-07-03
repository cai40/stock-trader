from __future__ import annotations

import pandas as pd

# Keller & Keuning VAA recency weights for ~1/3/6/12-month lookbacks (trading days).
LOOKBACKS_13612: tuple[tuple[int, int], ...] = ((21, 12), (63, 4), (126, 2), (252, 1))

# Aurum-style weights for 1/3/6/12-month lookbacks.
LOOKBACKS_AURUM: tuple[tuple[int, int], ...] = ((21, 1), (63, 2), (126, 4), (252, 6))


def trailing_return(close: pd.Series, at_index: int, lookback: int) -> float | None:
    """Total return over *lookback* trading days ending at *at_index*."""
    if at_index < lookback:
        return None
    start = float(close.iloc[at_index - lookback])
    if start <= 0:
        return None
    return float(close.iloc[at_index] / start - 1)


def weighted_momentum(
    close: pd.Series,
    at_index: int,
    lookbacks_weights: tuple[tuple[int, int], ...],
) -> float | None:
    """Sum of (weight × trailing return) for each lookback period."""
    score = 0.0
    for lookback, weight in lookbacks_weights:
        ret = trailing_return(close, at_index, lookback)
        if ret is None:
            return None
        score += weight * ret
    return score


def momentum_13612(close: pd.Series, at_index: int) -> float | None:
    """VAA 13612 recency-weighted momentum score."""
    return weighted_momentum(close, at_index, LOOKBACKS_13612)


def momentum_aurum(close: pd.Series, at_index: int) -> float | None:
    """Aurum-style multi-period momentum score."""
    return weighted_momentum(close, at_index, LOOKBACKS_AURUM)
