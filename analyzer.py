import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

from watchlist import TECH_GROWTH_SECTORS, get_sector, get_symbols

logger = logging.getLogger(__name__)


@dataclass
class StockAnalysis:
    symbol: str
    sector: str
    current_price: float
    weekly_rsi: float
    last_week_return: float
    avg_weekly_range_pct: float
    weekly_atr: float
    dist_from_52w_high: float
    dist_from_52w_low: float
    price_vs_20w_sma: float
    last_2_days_positive: bool
    last_day_positive: bool
    score: int
    score_reasons: List[str] = field(default_factory=list)


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _fetch_data(symbol: str) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    try:
        ticker = yf.Ticker(symbol)
        weekly = ticker.history(period="1y", interval="1wk", auto_adjust=True)
        daily = ticker.history(period="3mo", interval="1d", auto_adjust=True)
        if weekly.empty or daily.empty:
            logger.warning("No data returned for %s", symbol)
            return None, None
        return weekly, daily
    except Exception as exc:
        logger.error("Failed to fetch data for %s: %s", symbol, exc)
        return None, exc  # type: ignore[return-value]


def _analyze_stock(symbol: str, weekly: pd.DataFrame, daily: pd.DataFrame) -> Optional[StockAnalysis]:
    try:
        weekly = weekly.copy()
        daily = daily.copy()

        weekly.index = pd.to_datetime(weekly.index, utc=True).tz_convert(None)
        daily.index = pd.to_datetime(daily.index, utc=True).tz_convert(None)

        if len(weekly) < 20:
            logger.debug("Insufficient weekly data for %s", symbol)
            return None

        weekly["pct_range"] = (weekly["High"] - weekly["Low"]) / weekly["Low"] * 100
        weekly["weekly_return"] = weekly["Close"].pct_change() * 100

        weekly_rsi_series = _compute_rsi(weekly["Close"], period=14)
        weekly_rsi = float(weekly_rsi_series.iloc[-1]) if not weekly_rsi_series.empty else 50.0

        last_week_return = float(weekly["weekly_return"].iloc[-1])

        avg_weekly_range = float(weekly["pct_range"].tail(12).mean())

        high_low_diff = weekly["High"] - weekly["Low"]
        prev_close = weekly["Close"].shift(1)
        true_range = pd.concat(
            [
                high_low_diff,
                (weekly["High"] - prev_close).abs(),
                (weekly["Low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        weekly_atr = float(true_range.tail(12).mean())

        yearly_high = float(weekly["High"].max())
        yearly_low = float(weekly["Low"].min())
        current_price = float(daily["Close"].iloc[-1])

        dist_from_52w_high = (current_price - yearly_high) / yearly_high * 100
        dist_from_52w_low = (current_price - yearly_low) / yearly_low * 100

        sma_20w = float(weekly["Close"].tail(20).mean())
        price_vs_20w_sma = current_price / sma_20w

        if len(daily) >= 2:
            last_2_days_positive = (
                float(daily["Close"].iloc[-1]) > float(daily["Close"].iloc[-2])
                and float(daily["Close"].iloc[-2]) > float(daily["Close"].iloc[-3])
            ) if len(daily) >= 3 else float(daily["Close"].iloc[-1]) > float(daily["Close"].iloc[-2])
        else:
            last_2_days_positive = False

        last_day_positive = (
            float(daily["Close"].iloc[-1]) > float(daily["Close"].iloc[-2])
            if len(daily) >= 2
            else False
        )

        sector = get_sector(symbol)
        score, reasons = _compute_score(
            weekly_rsi=weekly_rsi,
            last_week_return=last_week_return,
            avg_weekly_range=avg_weekly_range,
            price_vs_20w_sma=price_vs_20w_sma,
            last_2_days_positive=last_2_days_positive,
            last_day_positive=last_day_positive,
            sector=sector,
        )

        return StockAnalysis(
            symbol=symbol,
            sector=sector,
            current_price=current_price,
            weekly_rsi=round(weekly_rsi, 2),
            last_week_return=round(last_week_return, 2),
            avg_weekly_range_pct=round(avg_weekly_range, 2),
            weekly_atr=round(weekly_atr, 2),
            dist_from_52w_high=round(dist_from_52w_high, 2),
            dist_from_52w_low=round(dist_from_52w_low, 2),
            price_vs_20w_sma=round(price_vs_20w_sma, 4),
            last_2_days_positive=last_2_days_positive,
            last_day_positive=last_day_positive,
            score=score,
            score_reasons=reasons,
        )
    except Exception as exc:
        logger.error("Error analyzing %s: %s", symbol, exc)
        return None


def _compute_score(
    weekly_rsi: float,
    last_week_return: float,
    avg_weekly_range: float,
    price_vs_20w_sma: float,
    last_2_days_positive: bool,
    last_day_positive: bool,
    sector: str,
) -> Tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []

    if weekly_rsi < 30:
        score += 3
        reasons.append(f"Weekly RSI very oversold ({weekly_rsi:.1f} < 30) +3")
    elif weekly_rsi < 40:
        score += 2
        reasons.append(f"Weekly RSI oversold ({weekly_rsi:.1f} < 40) +2")
    elif weekly_rsi < 50:
        score += 1
        reasons.append(f"Weekly RSI slightly oversold ({weekly_rsi:.1f} < 50) +1")

    if last_week_return < -5:
        score += 2
        reasons.append(f"Large weekly drop ({last_week_return:.1f}%) +2")
    elif last_week_return < -3:
        score += 1
        reasons.append(f"Moderate weekly drop ({last_week_return:.1f}%) +1")

    if avg_weekly_range > 7:
        score += 2
        reasons.append(f"Very high weekly volatility (avg range {avg_weekly_range:.1f}% > 7%) +2")
    elif avg_weekly_range > 5:
        score += 1
        reasons.append(f"High weekly volatility (avg range {avg_weekly_range:.1f}% > 5%) +1")

    if price_vs_20w_sma >= 0.85:
        score += 1
        reasons.append(f"Price within 15% of 20w SMA (ratio {price_vs_20w_sma:.2f}) +1")

    if last_2_days_positive:
        score += 2
        reasons.append("Last 2 days positive (bounce signal) +2")
    elif last_day_positive:
        score += 1
        reasons.append("Last day positive (early bounce) +1")

    if sector in TECH_GROWTH_SECTORS:
        score += 1
        reasons.append(f"Tech/growth sector ({sector}) +1")

    return score, reasons


def run_analysis(symbols: Optional[List[str]] = None, min_score: int = 4) -> List[StockAnalysis]:
    if symbols is None:
        symbols = get_symbols()

    results: List[StockAnalysis] = []

    for symbol in symbols:
        logger.info("Analyzing %s...", symbol)
        weekly, daily = _fetch_data(symbol)
        if weekly is None or not isinstance(daily, pd.DataFrame):
            continue
        analysis = _analyze_stock(symbol, weekly, daily)
        if analysis is not None and analysis.score >= min_score:
            results.append(analysis)

    results.sort(key=lambda x: x.score, reverse=True)
    top_candidates = results[:5]

    logger.info(
        "Analysis complete. %d/%d stocks scored >= %d. Returning top %d.",
        len(results),
        len(symbols),
        min_score,
        len(top_candidates),
    )
    return top_candidates
