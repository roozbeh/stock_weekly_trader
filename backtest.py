"""
Weekly swing trade backtester.

For each Monday in the past N weeks it:
  1. Reconstructs the signal using only data available up to (not including) that Monday.
  2. Enters at Monday's opening price.
  3. Checks intra-week daily bars to see whether the +TARGET% limit or -STOP% stop
     is hit first; if neither, closes at Friday's close (mark-to-market).
  4. Prints a full trade log and summary P&L.

No look-ahead bias: weekly/daily history is sliced to the simulation date before
scoring, so future candles are never visible to the signal logic.
"""

import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

from watchlist import TECH_GROWTH_SECTORS, get_sector, get_symbols

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── config ────────────────────────────────────────────────────────────────────
BUDGET: float = float(os.environ.get("BUDGET", 10_000))
TARGET_PCT: float = float(os.environ.get("TARGET_PCT", 5.0))
STOP_PCT: float = float(os.environ.get("STOP_PCT", 3.0))
MIN_SCORE: int = int(os.environ.get("MIN_SCORE", 4))
WEEKS_BACK: int = int(os.environ.get("WEEKS_BACK", 4))


# ── data helpers ──────────────────────────────────────────────────────────────

def _fetch_all(symbols: List[str], period: str = "6mo") -> Dict[str, pd.DataFrame]:
    """Download daily OHLCV for all symbols in one batch call."""
    print(f"Downloading daily data for {len(symbols)} symbols …")
    raw = yf.download(
        symbols,
        period=period,
        interval="1d",
        auto_adjust=True,
        group_by="ticker",
        progress=False,
        threads=True,
    )
    out: Dict[str, pd.DataFrame] = {}
    if isinstance(raw.columns, pd.MultiIndex):
        for sym in symbols:
            try:
                df = raw[sym].dropna(how="all")
                if not df.empty:
                    df.index = pd.to_datetime(df.index, utc=True).tz_convert(None)
                    out[sym] = df
            except KeyError:
                pass
    else:
        # single symbol download
        sym = symbols[0]
        raw.index = pd.to_datetime(raw.index, utc=True).tz_convert(None)
        out[sym] = raw.dropna(how="all")
    return out


def _to_weekly(daily: pd.DataFrame) -> pd.DataFrame:
    """Resample daily OHLCV to weekly (Monday-anchored)."""
    weekly = daily.resample("W-MON", closed="left", label="left").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    ).dropna(how="all")
    return weekly


# ── scoring (mirrors analyzer.py, operates on sliced data) ───────────────────

def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _score_stock(
    symbol: str,
    daily_hist: pd.DataFrame,   # daily data UP TO (not including) sim_date
) -> Tuple[int, float, float]:
    """Return (score, current_price, weekly_rsi). Returns (-1, 0, 0) on failure."""
    try:
        if len(daily_hist) < 30:
            return -1, 0.0, 0.0

        weekly = _to_weekly(daily_hist)
        if len(weekly) < 20:
            return -1, 0.0, 0.0

        weekly["pct_range"] = (weekly["High"] - weekly["Low"]) / weekly["Low"] * 100
        weekly["weekly_return"] = weekly["Close"].pct_change() * 100

        weekly_rsi_series = _compute_rsi(weekly["Close"], period=14)
        weekly_rsi = float(weekly_rsi_series.iloc[-1])
        last_week_return = float(weekly["weekly_return"].iloc[-1])
        avg_weekly_range = float(weekly["pct_range"].tail(12).mean())

        current_price = float(daily_hist["Close"].iloc[-1])
        sma_20w = float(weekly["Close"].tail(20).mean())
        price_vs_20w_sma = current_price / sma_20w

        last_2_days_positive = False
        last_day_positive = False
        if len(daily_hist) >= 3:
            c = daily_hist["Close"]
            last_2_days_positive = (float(c.iloc[-1]) > float(c.iloc[-2]) and
                                     float(c.iloc[-2]) > float(c.iloc[-3]))
        if len(daily_hist) >= 2:
            c = daily_hist["Close"]
            last_day_positive = float(c.iloc[-1]) > float(c.iloc[-2])

        sector = get_sector(symbol)
        score = 0

        if weekly_rsi < 30:
            score += 3
        elif weekly_rsi < 40:
            score += 2
        elif weekly_rsi < 50:
            score += 1

        if last_week_return < -5:
            score += 2
        elif last_week_return < -3:
            score += 1

        if avg_weekly_range > 7:
            score += 2
        elif avg_weekly_range > 5:
            score += 1

        if price_vs_20w_sma >= 0.85:
            score += 1

        if last_2_days_positive:
            score += 2
        elif last_day_positive:
            score += 1

        if sector in TECH_GROWTH_SECTORS:
            score += 1

        return score, current_price, weekly_rsi

    except Exception as exc:
        logger.debug("Scoring failed for %s: %s", symbol, exc)
        return -1, 0.0, 0.0


# ── trade outcome ─────────────────────────────────────────────────────────────

@dataclass
class TradeResult:
    symbol: str
    week_of: str          # Monday date string
    entry_price: float
    target_price: float
    stop_price: float
    exit_price: float
    exit_type: str        # "TARGET", "STOP", "CLOSE"
    pnl_pct: float
    pnl_dollars: float
    shares: int
    score: int
    weekly_rsi: float


def _simulate_trade(
    symbol: str,
    entry_price: float,
    target_price: float,
    stop_price: float,
    week_daily: pd.DataFrame,  # daily bars FOR the entry week (Mon–Fri)
    score: int,
    weekly_rsi: float,
    week_label: str,
) -> Optional[TradeResult]:
    """Walk intra-week daily bars to determine exit type and price."""
    if week_daily.empty or entry_price <= 0:
        return None

    risk_per_share = entry_price * (STOP_PCT / 100)
    risk_budget = BUDGET * 0.02
    raw_shares = risk_budget / risk_per_share if risk_per_share > 0 else 1
    shares = max(1, int(min(raw_shares, BUDGET / entry_price)))

    exit_price = float(week_daily["Close"].iloc[-1])
    exit_type = "CLOSE"

    for _, bar in week_daily.iterrows():
        # Check stop first (pessimistic — assumes intraday low hit before high)
        if bar["Low"] <= stop_price:
            exit_price = stop_price
            exit_type = "STOP"
            break
        if bar["High"] >= target_price:
            exit_price = target_price
            exit_type = "TARGET"
            break

    pnl_pct = (exit_price - entry_price) / entry_price * 100
    pnl_dollars = round((exit_price - entry_price) * shares, 2)

    return TradeResult(
        symbol=symbol,
        week_of=week_label,
        entry_price=round(entry_price, 2),
        target_price=round(target_price, 2),
        stop_price=round(stop_price, 2),
        exit_price=round(exit_price, 2),
        exit_type=exit_type,
        pnl_pct=round(pnl_pct, 2),
        pnl_dollars=pnl_dollars,
        shares=shares,
        score=score,
        weekly_rsi=round(weekly_rsi, 1),
    )


# ── main backtest loop ────────────────────────────────────────────────────────

def run_backtest(symbols: Optional[List[str]] = None, weeks_back: int = WEEKS_BACK) -> List[TradeResult]:
    if symbols is None:
        symbols = get_symbols()

    all_daily = _fetch_all(symbols, period="6mo")

    # Find the last N completed Mondays (not the current/future week)
    today = pd.Timestamp.today().normalize()
    # Walk back to find completed Mon–Fri weeks
    mondays: List[pd.Timestamp] = []
    candidate = today - pd.offsets.Week(weekday=0)  # last Monday
    # If today IS Monday, last completed week started the Monday before
    if today.weekday() == 0:
        candidate = today - pd.offsets.Week(weekday=0)
    for _ in range(weeks_back):
        mondays.append(candidate)
        candidate -= pd.Timedelta(weeks=1)
    mondays = sorted(mondays)

    print(f"\nBacktesting {weeks_back} weeks: {[m.date() for m in mondays]}\n")

    results: List[TradeResult] = []

    for monday in mondays:
        friday = monday + pd.Timedelta(days=4)
        week_label = str(monday.date())
        signals_this_week: List[Tuple[str, float, float, float, int, float]] = []

        for symbol in symbols:
            daily = all_daily.get(symbol)
            if daily is None or daily.empty:
                continue

            # Data available BEFORE Monday (strictly less than Monday)
            hist = daily[daily.index < monday]
            if len(hist) < 30:
                continue

            score, last_close, weekly_rsi = _score_stock(symbol, hist)
            if score < MIN_SCORE:
                continue

            # Entry = Monday's open (first bar of the week)
            week_bars = daily[(daily.index >= monday) & (daily.index <= friday)]
            if week_bars.empty:
                continue
            entry_price = float(week_bars["Open"].iloc[0])
            target_price = round(entry_price * (1 + TARGET_PCT / 100), 4)
            stop_price = round(entry_price * (1 - STOP_PCT / 100), 4)

            signals_this_week.append((symbol, entry_price, target_price, stop_price, score, weekly_rsi))

        if not signals_this_week:
            print(f"  Week {week_label}: no signals met score >= {MIN_SCORE}")
            continue

        # Take top 5 by score
        signals_this_week.sort(key=lambda x: x[4], reverse=True)
        signals_this_week = signals_this_week[:5]

        print(f"  Week {week_label}: {len(signals_this_week)} signal(s) — "
              f"{[s[0] for s in signals_this_week]}")

        for symbol, entry, target, stop, score, rsi in signals_this_week:
            week_bars = all_daily[symbol]
            week_bars = week_bars[(week_bars.index >= monday) & (week_bars.index <= friday)]
            result = _simulate_trade(symbol, entry, target, stop, week_bars, score, rsi, week_label)
            if result:
                results.append(result)

    return results


# ── reporting ─────────────────────────────────────────────────────────────────

def print_report(results: List[TradeResult]) -> None:
    if not results:
        print("\nNo trades were simulated.")
        return

    col_w = [8, 12, 8, 8, 8, 8, 7, 8, 8, 6, 5]
    header = (
        f"{'Symbol':<8} {'Week':<12} {'Entry':>8} {'Target':>8} {'Stop':>8} "
        f"{'Exit':>8} {'Type':<7} {'P&L %':>8} {'P&L $':>8} {'Shares':>6} {'Score':>5}"
    )
    sep = "─" * len(header)

    print("\n" + sep)
    print(header)
    print(sep)

    wins = losses = closes = 0
    total_pnl = 0.0

    for r in sorted(results, key=lambda x: (x.week_of, x.symbol)):
        sign = "+" if r.pnl_pct >= 0 else ""
        pnl_tag = f"{sign}{r.pnl_pct:.2f}%"
        pnl_dollar_tag = f"{sign}${r.pnl_dollars:,.0f}"
        print(
            f"{r.symbol:<8} {r.week_of:<12} {r.entry_price:>8.2f} {r.target_price:>8.2f} "
            f"{r.stop_price:>8.2f} {r.exit_price:>8.2f} {r.exit_type:<7} "
            f"{pnl_tag:>8} {pnl_dollar_tag:>8} {r.shares:>6} {r.score:>5}"
        )
        total_pnl += r.pnl_dollars
        if r.exit_type == "TARGET":
            wins += 1
        elif r.exit_type == "STOP":
            losses += 1
        else:
            closes += 1

    print(sep)

    total = len(results)
    win_rate = wins / total * 100 if total else 0
    avg_pnl = total_pnl / total if total else 0

    print(f"\n{'SUMMARY':}")
    print(f"  Total trades    : {total}")
    print(f"  Target hit (W)  : {wins}  ({win_rate:.0f}%)")
    print(f"  Stop hit   (L)  : {losses}  ({losses/total*100:.0f}%)" if total else "")
    print(f"  Closed flat     : {closes}  ({closes/total*100:.0f}%)" if total else "")
    print(f"  Total P&L       : {'+'if total_pnl>=0 else ''}${total_pnl:,.0f}")
    print(f"  Avg P&L/trade   : {'+'if avg_pnl>=0 else ''}${avg_pnl:,.0f}")
    print(f"  Budget assumed  : ${BUDGET:,.0f}")
    print(f"  Target / Stop   : +{TARGET_PCT}% / -{STOP_PCT}%")
    print(f"  Min signal score: {MIN_SCORE}")
    print()

    # Per-week breakdown
    from collections import defaultdict
    weekly: Dict[str, float] = defaultdict(float)
    for r in results:
        weekly[r.week_of] += r.pnl_dollars
    print("  Weekly P&L breakdown:")
    for wk in sorted(weekly):
        val = weekly[wk]
        print(f"    {wk}  {'+'if val>=0 else ''}${val:,.0f}")
    print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backtest weekly swing signals over past N weeks.")
    parser.add_argument("--weeks", type=int, default=WEEKS_BACK, help="How many completed weeks to test (default 4)")
    parser.add_argument("--min-score", type=int, default=MIN_SCORE, help="Minimum signal score (default 4)")
    parser.add_argument("--symbols", nargs="+", default=None, help="Override watchlist with specific tickers")
    args = parser.parse_args()

    MIN_SCORE = args.min_score

    trades = run_backtest(symbols=args.symbols, weeks_back=args.weeks)
    print_report(trades)
