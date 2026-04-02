from dataclasses import dataclass
from typing import List


@dataclass
class WatchlistEntry:
    symbol: str
    sector: str


WATCHLIST: List[WatchlistEntry] = [
    WatchlistEntry("META", "tech"),
    WatchlistEntry("NVDA", "tech"),
    WatchlistEntry("TSLA", "tech"),
    WatchlistEntry("AMD", "tech"),
    WatchlistEntry("AMZN", "tech"),
    WatchlistEntry("GOOGL", "tech"),
    WatchlistEntry("MSFT", "tech"),
    WatchlistEntry("AAPL", "tech"),
    WatchlistEntry("NFLX", "tech"),
    WatchlistEntry("CRM", "tech"),
    WatchlistEntry("PYPL", "tech"),
    WatchlistEntry("SNAP", "tech"),
    WatchlistEntry("UBER", "tech"),
    WatchlistEntry("COIN", "tech"),
    WatchlistEntry("PLTR", "tech"),
    WatchlistEntry("SQ", "tech"),
    WatchlistEntry("SHOP", "tech"),
    WatchlistEntry("ROKU", "tech"),
    WatchlistEntry("RBLX", "tech"),
    WatchlistEntry("NET", "tech"),
    WatchlistEntry("ZS", "tech"),
    WatchlistEntry("CRWD", "tech"),
    WatchlistEntry("DDOG", "tech"),
    WatchlistEntry("MDB", "tech"),
    WatchlistEntry("SMCI", "tech"),
    WatchlistEntry("ARM", "tech"),
    WatchlistEntry("AVGO", "tech"),
    WatchlistEntry("ORCL", "tech"),
    WatchlistEntry("ADBE", "tech"),
    WatchlistEntry("NOW", "tech"),
    WatchlistEntry("PANW", "tech"),
    WatchlistEntry("INTC", "tech"),
    WatchlistEntry("QCOM", "tech"),
    WatchlistEntry("MU", "tech"),
    WatchlistEntry("ON", "tech"),
    WatchlistEntry("MRVL", "tech"),
    WatchlistEntry("AMAT", "tech"),
    WatchlistEntry("LRCX", "tech"),
    WatchlistEntry("KLAC", "tech"),
    WatchlistEntry("TXN", "tech"),
]


TECH_GROWTH_SECTORS = {"tech", "growth"}


def get_symbols() -> List[str]:
    return [entry.symbol for entry in WATCHLIST]


def get_sector(symbol: str) -> str:
    for entry in WATCHLIST:
        if entry.symbol == symbol:
            return entry.sector
    return "unknown"
