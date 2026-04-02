import logging
import os
from datetime import date
from pathlib import Path
from typing import List

from signals import TradeSignal

logger = logging.getLogger(__name__)

REPORTS_DIR = Path(os.environ.get("REPORTS_DIR", "/app/reports"))

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Weekly Swing Trade Signals — {report_date}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0d1117;
    color: #c9d1d9;
    font-family: 'Segoe UI', system-ui, sans-serif;
    padding: 2rem;
  }}
  h1 {{ color: #58a6ff; margin-bottom: 0.25rem; font-size: 1.8rem; }}
  .subtitle {{ color: #8b949e; margin-bottom: 2rem; font-size: 0.9rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 1.5rem; }}
  .card {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 1.5rem;
    position: relative;
  }}
  .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }}
  .symbol {{ font-size: 1.5rem; font-weight: 700; color: #f0f6fc; }}
  .sector-badge {{
    background: #1f6feb;
    color: #fff;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
  }}
  .score-badge {{
    position: absolute;
    top: 1rem;
    right: 1rem;
    background: #238636;
    color: #fff;
    border-radius: 50%;
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 0.9rem;
  }}
  .action-line {{
    background: #0d419d22;
    border-left: 4px solid #58a6ff;
    border-radius: 4px;
    padding: 0.75rem 1rem;
    margin-bottom: 1rem;
    font-size: 0.95rem;
    line-height: 1.5;
  }}
  .prices {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.75rem; margin-bottom: 1rem; }}
  .price-box {{ background: #0d1117; border-radius: 8px; padding: 0.6rem; text-align: center; }}
  .price-label {{ font-size: 0.7rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em; }}
  .price-value {{ font-size: 1.1rem; font-weight: 700; margin-top: 2px; }}
  .entry {{ color: #f0f6fc; }}
  .target {{ color: #3fb950; }}
  .stoploss {{ color: #f85149; }}
  .stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; margin-bottom: 1rem; font-size: 0.82rem; }}
  .stat {{ background: #0d1117; border-radius: 6px; padding: 0.4rem 0.6rem; }}
  .stat-label {{ color: #8b949e; }}
  .stat-value {{ color: #c9d1d9; font-weight: 600; }}
  .position-box {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 1rem;
    font-size: 0.85rem;
  }}
  .position-box strong {{ color: #58a6ff; }}
  .reasons {{ font-size: 0.78rem; color: #8b949e; }}
  .reasons ul {{ padding-left: 1.2rem; margin-top: 0.3rem; }}
  .reasons li {{ margin-bottom: 2px; }}
  .chart-link {{ display: inline-block; margin-top: 0.75rem; color: #58a6ff; font-size: 0.82rem; text-decoration: none; }}
  .chart-link:hover {{ text-decoration: underline; }}
  .empty {{ text-align: center; padding: 3rem; color: #8b949e; font-size: 1.1rem; }}
  .footer {{ margin-top: 2rem; font-size: 0.78rem; color: #8b949e; text-align: center; }}
</style>
</head>
<body>
<h1>Weekly Swing Trade Signals</h1>
<p class="subtitle">Generated on {report_date} &mdash; Budget: ${budget:,.0f} &mdash; Target: +{target_pct}% / Stop: -{stop_pct}%</p>
{content}
<p class="footer">Data via Yahoo Finance (yfinance). Not financial advice. Always verify before trading.</p>
</body>
</html>
"""

_CARD_TEMPLATE = """\
<div class="card">
  <div class="score-badge">{score}</div>
  <div class="card-header">
    <span class="symbol">{symbol}</span>
    <span class="sector-badge">{sector}</span>
  </div>
  <div class="action-line">
    <strong>BUY {symbol}</strong> at <strong>${entry_price:.2f}</strong> &mdash;
    set limit sell at <strong>${target_price:.2f}</strong> (+{target_pct:.1f}%) &mdash;
    stop loss at <strong>${stop_loss_price:.2f}</strong> (-{stop_pct:.1f}%)
  </div>
  <div class="prices">
    <div class="price-box">
      <div class="price-label">Entry</div>
      <div class="price-value entry">${entry_price:.2f}</div>
    </div>
    <div class="price-box">
      <div class="price-label">Target (+{target_pct:.1f}%)</div>
      <div class="price-value target">${target_price:.2f}</div>
    </div>
    <div class="price-box">
      <div class="price-label">Stop (-{stop_pct:.1f}%)</div>
      <div class="price-value stoploss">${stop_loss_price:.2f}</div>
    </div>
  </div>
  <div class="stats">
    <div class="stat"><span class="stat-label">Weekly RSI: </span><span class="stat-value">{weekly_rsi:.1f}</span></div>
    <div class="stat"><span class="stat-label">Last Wk Return: </span><span class="stat-value">{last_week_return:+.1f}%</span></div>
    <div class="stat"><span class="stat-label">Avg Wkly Range: </span><span class="stat-value">{avg_weekly_range_pct:.1f}%</span></div>
    <div class="stat"><span class="stat-label">From 52w High: </span><span class="stat-value">{dist_from_52w_high:+.1f}%</span></div>
    <div class="stat"><span class="stat-label">From 52w Low: </span><span class="stat-value">{dist_from_52w_low:+.1f}%</span></div>
    <div class="stat"><span class="stat-label">vs 20w SMA: </span><span class="stat-value">{price_vs_20w_sma:.2f}x</span></div>
  </div>
  <div class="position-box">
    <strong>Position:</strong> {suggested_shares} shares &times; ${entry_price:.2f} =
    <strong>${suggested_capital:,.2f}</strong> &mdash; Max loss: <strong>${max_loss:.2f}</strong>
  </div>
  <div class="reasons">
    <strong>Score rationale:</strong>
    <ul>{reasons_html}</ul>
  </div>
  <a class="chart-link" href="https://finance.yahoo.com/chart/{symbol}" target="_blank" rel="noopener">
    View {symbol} chart on Yahoo Finance &rarr;
  </a>
</div>
"""


def _render_card(signal: TradeSignal) -> str:
    reasons_html = "".join(f"<li>{r}</li>" for r in signal.score_reasons)
    return _CARD_TEMPLATE.format(
        symbol=signal.symbol,
        sector=signal.sector,
        score=signal.score,
        entry_price=signal.entry_price,
        target_price=signal.target_price,
        stop_loss_price=signal.stop_loss_price,
        target_pct=signal.target_pct,
        stop_pct=signal.stop_pct,
        weekly_rsi=signal.weekly_rsi,
        last_week_return=signal.last_week_return,
        avg_weekly_range_pct=signal.avg_weekly_range_pct,
        dist_from_52w_high=signal.dist_from_52w_high,
        dist_from_52w_low=signal.dist_from_52w_low,
        price_vs_20w_sma=signal.price_vs_20w_sma,
        suggested_shares=signal.suggested_shares,
        suggested_capital=signal.suggested_capital,
        max_loss=signal.max_loss,
        reasons_html=reasons_html,
    )


def _render_terminal(signals: List[TradeSignal], report_date: str) -> str:
    lines: List[str] = []
    lines.append("=" * 70)
    lines.append(f"  WEEKLY SWING TRADE SIGNALS — {report_date}")
    lines.append("=" * 70)

    if not signals:
        lines.append("\n  No signals met the minimum score threshold today.\n")
        lines.append("=" * 70)
        return "\n".join(lines)

    for i, sig in enumerate(signals, 1):
        lines.append(f"\n  [{i}] {sig.symbol}  (Score: {sig.score})  |  {sig.sector.upper()}")
        lines.append(f"      BUY at:      ${sig.entry_price:.2f}")
        lines.append(f"      Sell target: ${sig.target_price:.2f}  (+{sig.target_pct:.1f}%)")
        lines.append(f"      Stop loss:   ${sig.stop_loss_price:.2f}  (-{sig.stop_pct:.1f}%)")
        lines.append(
            f"      Position:    {sig.suggested_shares} shares = "
            f"${sig.suggested_capital:,.2f}  |  Max loss: ${sig.max_loss:.2f}"
        )
        lines.append(f"      Weekly RSI:  {sig.weekly_rsi:.1f}")
        lines.append(f"      Last wk:     {sig.last_week_return:+.1f}%")
        lines.append(f"      Avg wkly rng:{sig.avg_weekly_range_pct:.1f}%")
        lines.append(f"      vs 20w SMA:  {sig.price_vs_20w_sma:.2f}x")
        lines.append(f"      From 52w hi: {sig.dist_from_52w_high:+.1f}%")
        lines.append("      Reasons:")
        for reason in sig.score_reasons:
            lines.append(f"        - {reason}")

    lines.append("\n" + "=" * 70)
    lines.append("  Data via Yahoo Finance. Not financial advice.")
    lines.append("=" * 70 + "\n")
    return "\n".join(lines)


def generate_report(signals: List[TradeSignal], dry_run: bool = False) -> str:
    report_date = date.today().isoformat()
    budget = float(os.environ.get("BUDGET", 10_000))
    target_pct = float(os.environ.get("TARGET_PCT", 5.0))
    stop_pct = float(os.environ.get("STOP_PCT", 3.0))

    terminal_output = _render_terminal(signals, report_date)
    print(terminal_output)

    if signals:
        cards_html = '<div class="grid">' + "".join(_render_card(s) for s in signals) + "</div>"
    else:
        cards_html = '<div class="empty">No signals met the minimum score threshold today. Check back next week.</div>'

    html = _HTML_TEMPLATE.format(
        report_date=report_date,
        budget=budget,
        target_pct=target_pct,
        stop_pct=stop_pct,
        content=cards_html,
    )

    report_path: str = ""
    if not dry_run:
        try:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            report_path = str(REPORTS_DIR / f"report_{report_date}.html")
            with open(report_path, "w", encoding="utf-8") as fh:
                fh.write(html)
            logger.info("HTML report saved to %s", report_path)
        except OSError as exc:
            logger.error("Failed to save HTML report: %s", exc)
    else:
        logger.info("Dry-run mode: HTML report not saved to disk.")

    return report_path
