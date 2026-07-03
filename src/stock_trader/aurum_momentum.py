from __future__ import annotations

import pandas as pd

from stock_trader.momentum_util import momentum_aurum
from stock_trader.multi_asset import align_histories, returns_from_prices

OFFENSIVE = ("SPY", "QQQ", "EFA", "EEM")
DEFENSIVE = ("TLT", "GLD", "SHY")
VOL_WINDOW = 20


def _vol_adjusted_score(prices: dict[str, pd.Series], returns: dict[str, pd.Series], symbol: str, at_index: int) -> float | None:
  raw = momentum_aurum(prices[symbol], at_index)
  if raw is None:
    return None
  window = returns[symbol].iloc[max(0, at_index - VOL_WINDOW + 1) : at_index + 1]
  vol = float(window.std())
  if vol <= 0:
    return raw
  return raw / vol


def _pick_aurum_holding(
  prices: dict[str, pd.Series],
  returns: dict[str, pd.Series],
  at_index: int,
) -> str:
  offensive_scores = {
    symbol: _vol_adjusted_score(prices, returns, symbol, at_index)
    for symbol in OFFENSIVE
    if symbol in prices
  }
  defensive_scores = {
    symbol: momentum_aurum(prices[symbol], at_index)
    for symbol in DEFENSIVE
    if symbol in prices
  }

  spy_score = offensive_scores.get("SPY")
  valid_off = {s: sc for s, sc in offensive_scores.items() if sc is not None}
  valid_def = {s: sc for s, sc in defensive_scores.items() if sc is not None}

  if not valid_off:
    return OFFENSIVE[0]

  best_off_symbol = max(valid_off, key=valid_off.get)
  best_off_score = valid_off[best_off_symbol]

  use_offensive = best_off_score > 0
  if spy_score is not None:
    use_offensive = use_offensive and best_off_score >= spy_score

  if use_offensive:
    return best_off_symbol

  return max(valid_def, key=valid_def.get) if valid_def else DEFENSIVE[-1]


def aurum_momentum_equity(
  histories: dict[str, pd.DataFrame],
  initial_cash: float,
) -> pd.Series:
  """Aurum-style multi-period momentum rotation with vol-adjusted offensive ranking."""
  index, prices = align_histories(histories)
  if index.empty:
    return pd.Series(dtype=float)

  returns = returns_from_prices(prices)
  equity = initial_cash
  equities: list[float] = []
  holding = OFFENSIVE[0]
  last_month = None

  for i, timestamp in enumerate(index):
    month = timestamp.to_period("M")
    if last_month is None or month != last_month:
      holding = _pick_aurum_holding(prices, returns, i)
      last_month = month

    equity *= 1.0 + float(returns[holding].iloc[i])
    equities.append(equity)

  return pd.Series(equities, index=index)
