# RNS Trader

A systematic trading signal detector for AIM-listed oil & gas companies,
built on the London Stock Exchange RNS (Regulatory News Service) feed.

---

## What it does

AIM-listed resource stocks often move sharply after a material announcement —
a drilling result, fundraise, or production update. RNS Trader detects these
moves by watching for an abnormal spike in trading volume combined with a
significant price change on the reaction day. A historical backtest across all
past announcements measures which announcement types, market setups, and timing
conditions have produced the best forward-looking outcomes.

---

## Signal logic

Every RNS event passes through 3 sequential filters:

```
RNS EVENT
    │
    ▼
┌─────────────────────────────────────┐
│ FILTER 1: Category                  │
│ Is this announcement worth watching?│
│                                     │
│ SKIP:  HOL, NRA, BOA, DSH, RAG,     │
│        TVR, NOA, CRO (routine admin)│
│ WATCH: UPD, MSC, IOE, ROI, FR, IR  │
│ HIGH:  DRL, ROI, FR, IR             │
└──────────────┬──────────────────────┘
               │ pass
               ▼
┌─────────────────────────────────────┐
│ FILTER 2: Context                   │
│ Is the stock in a tradeable setup?  │
│                                     │
│ Checks:                             │
│  · Price position in 52-week range  │
│  · Above/below 20-day moving avg    │
│  · Pre-announcement volume trend    │
│  · 60-day momentum                  │
│                                     │
│ Output: strong / neutral /          │
│         extended / skip             │
└──────────────┬──────────────────────┘
               │ pass
               ▼
┌─────────────────────────────────────┐
│ FILTER 3: Reaction detector         │
│ Did the market actually react?      │
│                                     │
│ Measures the daily bar on the       │
│ reaction day (same day for pre-     │
│ market/intraday, next day for       │
│ post-market announcements):         │
│                                     │
│ TRIGGER if BOTH:                    │
│  · Volume > 3.0× 20-day avg  AND   │
│  · Price move > 3.5%                │
│                                     │
│ Output: direction (BUY/SELL)        │
│         strength (e.g. 6.2×)        │
│         confidence (0.0–1.0)        │
└──────────────┬──────────────────────┘
               │ triggered
               ▼
        RECORD TRADE
        Entry: next trading day open
        Exits: T+1d, T+5d, T+20d close
        WIN / LOSS outcome per timeframe
```

---

## Entry & Exit logic (no same-bar bias)

A critical design decision: the reaction is detected using the **close** of the
reaction day bar. Entry is taken at the **next trading day's open**. This means:

- You observe the volume spike + price move after market close
- You enter at the open of the following morning
- Exits are measured at T+1d, T+5d, and T+20d closes

This prevents same-bar bias (where entry and exit are from the same bar that
triggered the signal, guaranteeing artificial wins).

---

## Current status

| Component | Status | Notes |
|-----------|--------|-------|
| Data collection | ✅ Working | 30 tickers, daily bars |
| Reaction detector | ✅ Working | Daily bar signal, no 5m bars |
| Backtest engine | ✅ Working | T+1d/T+5d/T+20d exits |
| Dashboard | ✅ Working | Flask, port 5001 |
| Live monitor | ✅ Working | Watches for new RNS intraday |
| LLM scoring | ⚠️ Optional | Requires xAI API key |
| Signal validation | 🔄 In progress | Clean backtest pending |
| Threshold optimisation | ❌ Not done | 3.0×/3.5% are starting points |
| Context filter validation | ❌ Not done | Not yet proven to add value |

---

## Known issues fixed

| Issue | Fix |
|-------|-----|
| Duplicate daily price bars (1013 instead of ~509) | `price_fetcher.py` now stores 1d bars as `YYYY-MM-DD` only, preventing timezone-offset duplicates from yfinance |
| Same-bar bias (99.6% win rate) | Entry moved to next day open, exits to T+1d/T+5d/T+20d closes |
| `ImportError: get_reaction_start` | Function added to `reaction_detector.py` |
| `KeyError: start_time` | `start_time` key added to `detect_reaction()` result dict |
| `UNIQUE constraint failed` on re-run | `INSERT OR REPLACE` in simulator |
| `database is locked` across tickers | `try/finally` on all `conn.close()` calls |
| Dashboard `no such column: outcome_eod` | Updated to `outcome_t5d` / `return_t5d` |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        RNS TRADER                           │
├──────────────┬──────────────┬──────────────┬────────────────┤
│   COLLECT    │   REACT      │   BACKTEST   │   DASHBOARD    │
│              │              │              │                │
│ rns_fetcher  │ category_    │ simulator.py │ app.py         │
│ .py          │ filter.py    │              │ index.html     │
│              │              │ analyser.py  │                │
│ price_       │ context_     │              │                │
│ fetcher.py   │ filter.py    │              │                │
│              │              │              │                │
│ database.py  │ reaction_    │              │                │
│              │ detector.py  │              │                │
└──────────────┴──────────────┴──────────────┴────────────────┘
         ↓              ↓              ↓
    SQLite DB      Signal logic    Results DB
    (rns_events,   (3 filters)     (backtest_
    price_bars)                     results)
```

---

## Data flow

```
SCHEDULED (daily, 07:30 UK):
  run_collect.py
      │
      ├─ LSE API → fetch new RNS for each ticker
      ├─ LSE API → fetch full body text for new RNS
      └─ Yahoo Finance → fetch daily price bars
             │
             ▼
         SQLite DB
         /data/matd_backtest.db
             │
             ├─ rns_events       (announcements)
             ├─ price_bars       (OHLCV, 1d)
             └─ backtest_results (signal outcomes)

ON DEMAND:
  run_backtest.py
      │
      └─ Loops all tickers × all RNS events
         Runs 3 filters, detects reactions,
         records T+1d/T+5d/T+20d returns

  run_analyse.py
      │
      └─ Reads backtest_results, prints
         win rates, avg returns, profit factor
         by ticker / category / timing / strength

ALWAYS ON (systemd service):
  run_dashboard.py → Flask on port 5001
      │
      ├─ GET /              → Summary tab
      ├─ GET /chart-data    → Price Chart tab
      ├─ GET /backtest-data → Analysis tab
      └─ GET /rns/<id>      → Drawer detail
```

---

## Tickers (30 AIM oil & gas)

| Ticker | Company |
|--------|---------|
| MATD | Petro Matad Limited |
| 88E  | 88 Energy Ltd |
| CHAR | Chariot Limited |
| PTAL | PetroTal Corporation |
| UJO  | Union Jack Oil plc |
| ZEN  | Zenith Energy Ltd |
| BOR  | Borders & Southern Petroleum plc |
| AXL  | Arrow Exploration Corp |
| PANR | Pantheon Resources plc |
| KIST | Kistos Holdings plc |
| BLOE | Block Energy plc |
| RKH  | Rockhopper Exploration |
| ECO  | Eco Atlantic Oil & Gas |
| AET  | Afentra |
| FOG  | Falcon Oil & Gas |
| SEI  | Sintana Energy |
| JSE  | Jadestone Energy |
| ZPHR | Zephyr Energy |
| SEA  | Seascape Energy Asia |
| JOG  | Jersey Oil and Gas |
| TXP  | Touchstone Exploration |
| PMG  | Parkmead Group |
| STAR | Star Energy Group |
| ENW  | Enwell Energy |
| PXEN | Prospex Energy |
| EOG  | Europa Oil & Gas |
| ORCA | Orcadian Energy |
| EPP  | EnergyPathways |
| SOU  | Sound Energy |
| UOG  | United Oil & Gas |

---

## File map

```
rns-trader/
├── config/
│   └── settings.py              # All constants, ticker list, API keys
├── src/
│   ├── collect/
│   │   ├── database.py          # SQLite schema + connection helper
│   │   ├── rns_fetcher.py       # LSE API: RNS list + body fetch
│   │   ├── price_fetcher.py     # Yahoo Finance OHLCV (1d bars)
│   │   └── html_cleaner.py      # Strip HTML from RNS body text
│   ├── react/
│   │   ├── category_filter.py   # Filter 1: skip/watch/high priority
│   │   ├── context_filter.py    # Filter 2: price setup quality
│   │   └── reaction_detector.py # Filter 3: volume + price spike
│   ├── backtest/
│   │   ├── simulator.py         # Main backtest loop
│   │   └── analyser.py          # Results analysis + reporting
│   ├── monitor/
│   │   └── live_monitor.py      # Intraday RNS watcher
│   └── score/
│       ├── scorer.py            # Grok LLM scoring (optional)
│       └── prompts.py           # LLM prompt templates
├── scripts/
│   ├── run_collect.py           # Collect RNS + price data
│   ├── run_backtest.py          # Run backtest (all or specific tickers)
│   ├── run_analyse.py           # Print backtest analysis to terminal
│   ├── run_monitor.py           # Start live intraday monitor
│   ├── run_dashboard.py         # Start Flask dashboard
│   ├── reset_backtest_db.py     # Drop + recreate backtest_results table
│   ├── dedup_price_bars.py      # Remove duplicate daily price bars
│   └── extract_features.py      # Feature extraction utility
└── dashboard/
    ├── app.py                   # Flask routes + SQL queries
    └── templates/
        └── index.html           # Single-page dashboard UI
```

---

## Setup

### Requirements

- Raspberry Pi (or any Linux box)
- Python 3.10+
- Internet access to LSE and Yahoo Finance

### Install

```bash
git clone https://github.com/DanMavr/rns-trader.git
cd rns-trader
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configure

Edit `config/settings.py` and set your xAI API key if using LLM scoring.

### First run (full setup)

```bash
# 1. Collect all data (~10-20 mins for 30 tickers)
python scripts/run_collect.py

# 2. Remove any duplicate price bars
python scripts/dedup_price_bars.py

# 3. Run backtest
python scripts/run_backtest.py

# 4. Review results in terminal
python scripts/run_analyse.py

# 5. Start dashboard
python scripts/run_dashboard.py
# Open http://raspberrypi.local:5001
```

### Re-running the backtest

```bash
# Standard re-run (INSERT OR REPLACE - safe to repeat)
python scripts/run_backtest.py

# Wipe results and start clean
python scripts/reset_backtest_db.py
python scripts/run_backtest.py

# Single ticker
python scripts/run_backtest.py MATD

# With Grok LLM scoring
python scripts/run_backtest.py --llm
```

### Run as a service (Raspberry Pi)

```bash
sudo systemctl enable rns-trader-dashboard
sudo systemctl start rns-trader-dashboard
```

---

## Database schema

### `rns_events`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | LSE announcement ID (primary key) |
| ticker | TEXT | Stock ticker |
| category | TEXT | LSE category code (DRL, UPD, FR etc.) |
| headlinename | TEXT | Human-readable category name |
| title | TEXT | Announcement title |
| datetime | TEXT | Publication datetime (ISO 8601) |
| body_text | TEXT | Full announcement text (cleaned HTML) |
| fetch_status | TEXT | pending / ok / error / no_content |

### `price_bars`
| Column | Type | Description |
|--------|------|-------------|
| ticker | TEXT | Stock ticker |
| interval | TEXT | 1d only (5m not collected in backtest) |
| datetime | TEXT | YYYY-MM-DD for 1d bars |
| open/high/low/close | REAL | Price in pence |
| volume | INTEGER | Shares traded |

### `backtest_results`
| Column | Type | Description |
|--------|------|-------------|
| rns_id | INTEGER | FK → rns_events.id (UNIQUE) |
| ticker | TEXT | Stock ticker |
| timing | TEXT | pre_market / intraday / post_market |
| category | TEXT | LSE category code |
| skipped_category | INTEGER | 1 if skipped by filter 1 |
| setup_quality | TEXT | strong / neutral / extended / skip |
| skipped_context | INTEGER | 1 if skipped by filter 2 |
| reaction_triggered | INTEGER | 1 if volume+price spike detected |
| reaction_strength | REAL | Volume multiple (e.g. 6.2) |
| reaction_direction | INTEGER | 1=up, -1=down |
| reaction_confidence | REAL | 0.0–1.0 |
| reaction_price_chg | REAL | % price change on reaction day |
| reaction_date | TEXT | Date of reaction bar (YYYY-MM-DD) |
| avg_vol_20d | REAL | 20-day average daily volume |
| immediate_vol | REAL | Volume on reaction day |
| would_trade | INTEGER | 1 if all filters passed |
| direction | TEXT | BUY / SELL |
| entry_price | REAL | Next day open price (pence) |
| entry_time | TEXT | Next day date (YYYY-MM-DD) |
| price_t1d | REAL | Close price T+1 trading day |
| price_t5d | REAL | Close price T+5 trading days |
| price_t20d | REAL | Close price T+20 trading days |
| return_t1d | REAL | % return at T+1d |
| return_t5d | REAL | % return at T+5d |
| return_t20d | REAL | % return at T+20d |
| outcome_t1d | TEXT | WIN / LOSS at T+1d |
| outcome_t5d | TEXT | WIN / LOSS at T+5d |
| outcome_t20d | TEXT | WIN / LOSS at T+20d |
| llm_score | INTEGER | Grok score (optional) |

---

## Category codes

| Code | Description | Priority |
|------|-------------|----------|
| DRL | Drilling / well results | HIGH |
| FR  | Final results | HIGH |
| IR  | Interim results | HIGH |
| ROI | Results of placing / offer | HIGH |
| UPD | Operational update | WATCH |
| MSC | Miscellaneous | WATCH |
| IOE | Issue of equity | WATCH |
| CNT | Contract award | WATCH |
| ACQ | Acquisition | WATCH |
| HOL | Major holdings notification | SKIP |
| BOA | Board changes | SKIP |
| NOA | Notice of AGM | SKIP |
| RAG | Result of AGM | SKIP |
| NRA | Non-regulatory announcement | SKIP |
| DSH | Director shareholding | SKIP |
| TVR | Total voting rights | SKIP |
| CRO | Change of registered office | SKIP |

---

## What has and has not been validated

| Claim | Validated? |
|-------|-----------|
| Category skip list removes noise | Reasonable assumption — not statistically tested |
| Context filter (setup_quality) adds value | ❌ Not tested — only 26/2407 events skipped |
| 3.0× volume threshold is optimal | ❌ Not optimised — starting point only |
| 3.5% price move threshold is optimal | ❌ Not optimised — starting point only |
| T+5d is the best exit timeframe | ❌ Pending clean backtest results |
| Signal has genuine forward-looking edge | 🔄 Pending — clean backtest in progress |

---

## LLM scoring (optional)

When run with `--llm`, each triggered event is scored by Grok (xAI):

- Assesses announcement quality and likely market impact
- Score stored alongside reaction signal data
- Intended for future use as an additional filter layer
- **Not currently used in trade decision logic**

---

## Honest caveats

- **Small sample**: ~241 trades across 30 tickers over ~2 years
- **Survivorship bias**: tickers were selected because they are known/followed
- **Execution slippage**: entering at next-day open on low-liquidity AIM stocks after a volume spike will rarely achieve the theoretical open price
- **No risk management**: backtest treats all trades equally with no position sizing, stop losses, or maximum concurrent positions
- **Thresholds not optimised**: 3.0×/3.5% were chosen as sensible starting points, not derived from data
