# Project Context for Claude

## What This Is

A weekly stock swing trade signal generator built for a user who noticed that under the current political climate (Trump tariff announcements etc.), large-cap tech stocks swing dramatically within a single week — often 5–10% down then back up. The goal is to catch those bounces.

**User constraints:**
- Max $10,000 investment
- Buy once a week, set a limit sell (e.g. +5%) and walk away
- Full-time job — zero time to monitor intraday
- No paid APIs — free data only (Yahoo Finance via `yfinance`)
- Wants everything in Docker so it can run on a cheap cloud VM unattended

---

## Current State (as of 2026-04-02)

All core files are implemented and pushed to branch `claude/stock-swing-signals-vzZGf`.

### What is done
- `watchlist.py` — 40 high-volatility S&P 500 tickers (all tagged `tech` sector)
- `analyzer.py` — scoring engine: weekly RSI, weekly range %, bounce detection, 20w SMA ratio
- `signals.py` — converts scores to TradeSignal with entry/target/stop + position sizing
- `report.py` — dark-theme HTML report + terminal output
- `main.py` — CLI entry point (`--dry-run`, `--symbols`, `--min-score`)
- `scheduler.py` — runs every Monday at 14:35 UTC (9:35am ET) via `schedule` library
- `backtest.py` — historical simulation with no look-ahead bias, prints trade log + P&L summary
- `Dockerfile` + `docker-compose.yml` — fully containerized
- `requirements.txt` — pinned deps

### What is NOT done yet
- **Backtest has not been run** — the sandbox environment has no internet access (Yahoo Finance blocked at proxy), so `backtest.py` was written and syntax-checked but not executed. User needs to run it on their own machine.
- **No broker integration** — signals are output only (HTML + terminal). Execution is manual.
- **No alerting** — no email/SMS/push notification when signals are generated. Planned future work.
- **No web UI** — reports are static HTML files in `./reports/`. Planned future work.

---

## Architecture Decisions

### Scoring algorithm (in `analyzer.py` `_compute_score`)
Points-based system, max ~12 points, threshold = 4:
- RSI < 30: +3, RSI < 40: +2, RSI < 50: +1
- Last week return < -5%: +2, < -3%: +1
- Avg weekly range > 7%: +2, > 5%: +1
- Price ≥ 85% of 20-week SMA: +1 (not in freefall)
- Last 2 days positive (bounce): +2; last day positive: +1
- Tech/growth sector: +1

### Position sizing (in `signals.py`)
- Risk budget = 2% of BUDGET (e.g. $200 on $10k)
- Shares = min(risk_budget / (entry × stop_pct), BUDGET / entry)
- This means max loss per trade ≈ $200 regardless of stock price

### Backtest methodology (in `backtest.py`)
- Downloads 6 months of daily data upfront for all symbols
- Resamples daily → weekly on-the-fly per simulation date (avoids pre-computing weekly bars that would include future data)
- Entry = Monday open (first bar of the week)
- Exit logic: walk daily bars, check intraday low vs stop first (pessimistic), then high vs target
- Falls back to Friday close if neither hit

---

## Key Files and Where Things Live

| Concern | File | Key function/class |
|---|---|---|
| Watchlist | `watchlist.py` | `WATCHLIST`, `get_symbols()`, `get_sector()` |
| Data fetch | `analyzer.py` | `_fetch_data()` |
| Scoring | `analyzer.py` | `_compute_score()`, `_analyze_stock()` |
| Signal gen | `signals.py` | `generate_signals()`, `TradeSignal` dataclass |
| HTML report | `report.py` | `generate_report()`, `_render_card()` |
| Entry point | `main.py` | `run_pipeline()` |
| Scheduler | `scheduler.py` | `schedule.every().monday.at(...)` |
| Backtest | `backtest.py` | `run_backtest()`, `_simulate_trade()`, `print_report()` |

---

## Environment Variables

| Variable | Default | Notes |
|---|---|---|
| `BUDGET` | `10000` | USD, used for position sizing |
| `TARGET_PCT` | `5.0` | Limit sell % above entry |
| `STOP_PCT` | `3.0` | Stop loss % below entry |
| `SCHEDULE_TIME_UTC` | `14:35` | Monday run time in UTC |
| `MIN_SCORE` | `4` | Minimum score for a signal |
| `REPORTS_DIR` | `/app/reports` | Where HTML reports are saved |

---

## Likely Next Tasks (user hasn't asked yet)

1. **Run the backtest** — user wants a clear yes/no on whether the strategy is profitable. Needs internet access. Run `python backtest.py --weeks 8` and interpret results.

2. **Email/Slack alerts** — user has a full-time job, they won't check the HTML report. A simple SMTP or Slack webhook notification when signals are generated would make this practical.

3. **Broker integration** — Alpaca has a free paper-trading API. Could auto-place the buy order + limit sell order on Monday morning.

4. **Expand watchlist** — currently all tickers are tagged `tech`. Could add ETFs like SOXS/TQQQ for leveraged plays, or sector-specific high-beta stocks.

5. **Signal tuning** — once the backtest runs, scoring weights may need adjustment based on actual win rate.

6. **Web dashboard** — simple Flask/FastAPI app to serve the HTML reports with a list of past signals and outcomes.

---

## Running Locally (reminder)

```bash
# Install deps
pip install -r requirements.txt

# One-shot signal run
python main.py

# Backtest last 4 weeks
python backtest.py --weeks 4

# Docker one-shot
docker compose run --rm stock-signals python scheduler.py --now

# Docker scheduled (stays running)
docker compose up -d
```

---

## Git Branch

All work is on: `claude/stock-swing-signals-vzZGf`
Repo: `roozbeh/stock_weekly_trader`
