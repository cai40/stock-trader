from __future__ import annotations

import pandas as pd

from stock_trader.momentum_util import momentum_13612
from stock_trader.multi_asset import align_histories, returns_from_prices

# VAA-G4 aggressive universe (Keller & Keuning).
OFFENSIVE = ("SPY", "EFA", "EEM", "IWM")
DEFENSIVE = ("LQD", "IEF", "SHY")
BREADTH_THRESHOLD = 1
TOP_OFFENSIVE = 1


def _pick_vaa_holding(
  prices: dict[str, pd.Series],
  at_index: int,
) -> str:
  offensive_scores = {
    symbol: momentum_13612(prices[symbol], at_index)
    for symbol in OFFENSIVE
    if symbol in prices
  }
  defensive_scores = {
    symbol: momentum_13612(prices[symbol], at_index)
    for symbol in DEFENSIVE
    if symbol in prices
  }

  if any(score is None for score in offensive_scores.values()):
    return OFFENSIVE[0]

  negative_breadth = sum(1 for score in offensive_scores.values() if score is not None and score < 0)

  if negative_breadth >= BREADTH_THRESHOLD:
    valid_def = {s: sc for s, sc in defensive_scores.items() if sc is not None}
    return max(valid_def, key=valid_def.get) if valid_def else DEFENSIVE[-1]

  ranked = sorted(
    ((symbol, score) for symbol, score in offensive_scores.items() if score is not None),
    key=lambda item: item[1],
    reverse=True,
  )
  return ranked[0][0] if ranked else OFFENSIVE[0]


def vaa_equity(
  histories: dict[str, pd.DataFrame],
  initial_cash: float,
) -> pd.Series:
  """Vigilant Asset Allocation (VAA-G4): breadth momentum rotation among ETFs."""
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
      holding = _pick_vaa_holding(prices, i)
      last_month = month

    equity *= 1.0 + float(returns[holding].iloc[i])
    equities.append(equity)

  return pd.Series(equities, index=index)
