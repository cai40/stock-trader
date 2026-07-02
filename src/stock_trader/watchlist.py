from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WatchlistItem:
    symbol: str
    label: str


WATCHLIST: tuple[WatchlistItem, ...] = (
    WatchlistItem("VGT", "VGT — Vanguard Info Tech ETF"),
    WatchlistItem("SPY", "SPY — S&P 500 ETF"),
    WatchlistItem("TE", "TE — TECO Energy"),
    WatchlistItem("AAPL", "AAPL — Apple"),
    WatchlistItem("MSFT", "MSFT — Microsoft"),
    WatchlistItem("NVDA", "NVDA — NVIDIA"),
    WatchlistItem("GOOGL", "GOOGL — Alphabet"),
    WatchlistItem("AMZN", "AMZN — Amazon"),
    WatchlistItem("META", "META — Meta"),
    WatchlistItem("QQQ", "QQQ — Nasdaq 100 ETF"),
    WatchlistItem("XLK", "XLK — Technology Select Sector ETF"),
    WatchlistItem("VOO", "VOO — Vanguard S&P 500 ETF"),
)


CUSTOM_OPTION = "Custom ticker..."


def watchlist_labels() -> list[str]:
    return [item.label for item in WATCHLIST]


def label_to_symbol(label: str) -> str | None:
    for item in WATCHLIST:
        if item.label == label:
            return item.symbol
    return None


def watchlist_select_options() -> list[str]:
    return watchlist_labels() + [CUSTOM_OPTION]
