import os
from dataclasses import dataclass
from typing import List

from analyzer import StockAnalysis


@dataclass
class TradeSignal:
    symbol: str
    sector: str
    entry_price: float
    target_price: float
    stop_loss_price: float
    target_pct: float
    stop_pct: float
    suggested_shares: int
    suggested_capital: float
    max_loss: float
    score: int
    score_reasons: List[str]
    weekly_rsi: float
    last_week_return: float
    avg_weekly_range_pct: float
    dist_from_52w_high: float
    dist_from_52w_low: float
    price_vs_20w_sma: float


def _get_float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def generate_signals(candidates: List[StockAnalysis]) -> List[TradeSignal]:
    budget = _get_float_env("BUDGET", 10_000.0)
    target_pct = _get_float_env("TARGET_PCT", 5.0)
    stop_pct = _get_float_env("STOP_PCT", 3.0)

    risk_per_trade = budget * 0.02
    signals: List[TradeSignal] = []

    for stock in candidates:
        entry = stock.current_price
        target = round(entry * (1 + target_pct / 100), 2)
        stop = round(entry * (1 - stop_pct / 100), 2)

        risk_per_share = entry * (stop_pct / 100)
        if risk_per_share <= 0:
            continue

        raw_shares = risk_per_trade / risk_per_share
        max_shares_by_budget = budget / entry
        suggested_shares = max(1, int(min(raw_shares, max_shares_by_budget)))
        suggested_capital = round(suggested_shares * entry, 2)
        max_loss = round(suggested_shares * risk_per_share, 2)

        signals.append(
            TradeSignal(
                symbol=stock.symbol,
                sector=stock.sector,
                entry_price=round(entry, 2),
                target_price=target,
                stop_loss_price=stop,
                target_pct=target_pct,
                stop_pct=stop_pct,
                suggested_shares=suggested_shares,
                suggested_capital=suggested_capital,
                max_loss=max_loss,
                score=stock.score,
                score_reasons=stock.score_reasons,
                weekly_rsi=stock.weekly_rsi,
                last_week_return=stock.last_week_return,
                avg_weekly_range_pct=stock.avg_weekly_range_pct,
                dist_from_52w_high=stock.dist_from_52w_high,
                dist_from_52w_low=stock.dist_from_52w_low,
                price_vs_20w_sma=stock.price_vs_20w_sma,
            )
        )

    return signals
