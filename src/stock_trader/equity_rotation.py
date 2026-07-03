from __future__ import annotations

import pandas as pd

from stock_trader.momentum_util import trailing_return
from stock_trader.multi_asset import align_histories, returns_from_prices

ROTATION_UNIVERSE = ("SPY", "QQQ", "VGT")
SAFE_ASSET = "SHY"
LOOKBACK = 63
TREND_WINDOW = 200


def _regime_allows_risk(spy_close: pd.Series, at_index: int) -> bool:
  if at_index < TREND_WINDOW:
    return True
  price = float(spy_close.iloc[at_index])
  trend = float(spy_close.iloc[max(0, at_index - TREND_WINDOW + 1) : at_index + 1].mean())
  return price >= trend


def _pick_rotation_holding(
  prices: dict[str, pd.Series],
  at_index: int,
) -> str:
  if "SPY" in prices and not _regime_allows_risk(prices["SPY"], at_index):
    return SAFE_ASSET

  scores = {
    symbol: trailing_return(prices[symbol], at_index, LOOKBACK)
    for symbol in ROTATION_UNIVERSE
    if symbol in prices
  }
  valid = {symbol: score for symbol, score in scores.items() if score is not None}
  if not valid:
    return ROTATION_UNIVERSE[0]
  return max(valid, key=valid.get)


def equity_rotation_equity(
  histories: dict[str, pd.DataFrame],
  initial_cash: float,
) -> pd.Series:
  """Monthly rotation among SPY/QQQ/VGT by 3-month momentum with SPY 200d MA regime filter."""
  index, prices = align_histories(histories)
  if index.empty:
    return pd.Series(dtype=float)

  returns = returns_from_prices(prices)
  equity = initial_cash
  equities: list[float] = []
  holding = ROTATION_UNIVERSE[0]
  last_month = None

  for i, timestamp in enumerate(index):
    month = timestamp.to_period("M")
    if last_month is None or month != last_month:
      holding = _pick_rotation_holding(prices, i)
      last_month = month

    equity *= 1.0 + float(returns[holding].iloc[i])
    equities.append(equity)

  return pd.Series(equities, index=index)
