# Stock Weekly Swing Trader

A weekly swing trade signal generator that scans ~40 high-volatility S&P 500 stocks every Monday morning and outputs buy/sell signals based on oversold conditions and volatility patterns.

**Free data only** — uses Yahoo Finance via `yfinance`, no paid API keys required.

---

## How It Works

Every Monday at 9:35am ET the system:
1. Downloads weekly + daily price history for the watchlist
2. Scores each stock using RSI, weekly range, bounce signals, and SMA proximity
3. Generates signals for stocks scoring ≥ 4 (top 5 at most)
4. Outputs a terminal report and saves an HTML report to `./reports/`

**Example signal output:**
```
[1] META  (Score: 7)  |  TECH
    BUY at:      $579.23
    Sell target: $608.19  (+5.0%)
    Stop loss:   $561.85  (-3.0%)
    Position:    17 shares = $9,847.00  |  Max loss: $295.42
    Weekly RSI:  28.4
    Last wk:     -6.2%
```

---

## Scoring Algorithm

| Condition | Points |
|---|---|
| Weekly RSI < 30 (very oversold) | +3 |
| Weekly RSI 30–40 (oversold) | +2 |
| Weekly RSI 40–50 (slightly oversold) | +1 |
| Last week return < -5% (big drop) | +2 |
| Last week return < -3% (moderate drop) | +1 |
| Avg weekly range > 7% (very volatile) | +2 |
| Avg weekly range > 5% (volatile) | +1 |
| Price within 15% of 20-week SMA | +1 |
| Last 2 days positive (bounce signal) | +2 |
| Last day positive (early bounce) | +1 |
| Tech/growth sector | +1 |

Signals are only generated for stocks with **score ≥ 4**.

---

## Position Sizing

- Risk per trade = 2% of budget (e.g. $200 on a $10k budget)
- Shares = `risk_per_trade / (entry_price × stop_pct)`
- Capped so total position never exceeds full budget

---

## Quick Start

### Option A — Docker (recommended for cloud)

```bash
# Clone the repo
git clone <your-repo-url>
cd stock_weekly_trader

# Create reports directory
mkdir -p reports

# Run once right now
docker compose run --rm stock-signals python scheduler.py --now

# Or start the scheduler (runs every Monday 9:35am ET)
docker compose up -d

# View logs
docker compose logs -f
```

Reports are saved to `./reports/report_YYYY-MM-DD.html` — open in any browser.

### Option B — Local Python

```bash
pip install -r requirements.txt

# Run once
python main.py

# Run the scheduler (stays running, fires every Monday)
python scheduler.py

# Dry run (no HTML saved)
python main.py --dry-run

# Test specific tickers only
python main.py --symbols META NVDA TSLA --min-score 3
```

---

## Backtesting

Run a simulation over the past N weeks to check historical signal performance:

```bash
# Local
python backtest.py --weeks 4

# Docker
docker compose run --rm stock-signals python backtest.py --weeks 4
```

**How the backtest works:**
- Steps back through each completed Monday for the past N weeks
- For each Monday, reconstructs signals using **only data available at that point** (no look-ahead bias)
- Entry = Monday's actual open price
- Checks each daily bar that week: if the intraday high hits `+TARGET%` → win; if intraday low hits `-STOP%` → loss; otherwise closes at Friday's close
- Prints a trade log and win rate / total P&L summary

**Options:**
```bash
python backtest.py --weeks 8          # go back 8 weeks
python backtest.py --min-score 5      # stricter signal filter
python backtest.py --symbols META NVDA TSLA  # specific tickers only
```

---

## Configuration

All settings are environment variables — set them in `docker-compose.yml` or export before running locally.

| Variable | Default | Description |
|---|---|---|
| `BUDGET` | `10000` | Max capital to deploy per week (USD) |
| `TARGET_PCT` | `5.0` | Limit sell target above entry (%) |
| `STOP_PCT` | `3.0` | Stop loss below entry (%) |
| `SCHEDULE_TIME_UTC` | `14:35` | When to run each Monday (UTC) |
| `MIN_SCORE` | `4` | Minimum score to generate a signal |
| `REPORTS_DIR` | `/app/reports` | Where HTML reports are saved |

**Timezone note:** `14:35 UTC` = `9:35am ET (EST)` / `10:35am ET (EDT, summer)`. If you want 9:35am year-round, use `13:35` during summer months (EDT).

---

## File Structure

```
stock_weekly_trader/
├── watchlist.py      # ~40 high-volatility S&P 500 tickers
├── analyzer.py       # Downloads data, scores each stock
├── signals.py        # Converts scores to buy/target/stop signals
├── report.py         # Terminal + HTML report generator
├── main.py           # One-shot pipeline entry point
├── scheduler.py      # Runs main.py every Monday at market open
├── backtest.py       # Historical simulation with P&L reporting
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── reports/          # Generated HTML reports land here
```

---

## Deploying to the Cloud

Any VM or container service works. Cheapest options:

- **Fly.io** — `fly launch` + `fly deploy`, free tier available
- **Railway** — connect GitHub repo, set env vars, deploy
- **DigitalOcean Droplet** — `docker compose up -d` on a $4/mo droplet
- **AWS EC2 / GCP / Azure** — any small instance with Docker installed

The container runs the scheduler continuously and wakes up each Monday. Reports accumulate in the mounted `./reports/` volume.

---

## Disclaimer

This tool is for informational and educational purposes only. It is not financial advice. Always verify signals independently before placing real trades. Past backtest performance does not guarantee future results.
