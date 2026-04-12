# RNS Trader

A systematic trading signal detector for AIM-listed oil & gas companies, built on the London Stock Exchange RNS (Regulatory News Service) feed.

---

## What it does

AIM-listed resource stocks often move sharply in the first minutes of trading after a material announcement — a drilling result, fundraise, or production update. RNS Trader detects these moves by watching for an abnormal spike in trading volume combined with a significant price change at open. A historical backtest across all past announcements shows which announcement types, market setups, and timing conditions have produced the best outcomes.

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
│ SKIP:  NOA, RAG, BOA, NRA, AGR      │
│        (routine admin)              │
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
│  · 60-day momentum (skip if >150%)  │
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
│ Measures first 3 × 5-min bars       │
│ after announcement window opens:    │
│                                     │
│ TRIGGER if:                         │
│  · Volume > 4× 20-day average  AND  │
│  · Price move > 3.5%                │
│                                     │
│ Output: direction (BUY/SELL)        │
│         strength (e.g. 6.2×)        │
│         confidence (0.0–1.0)        │
└──────────────┬──────────────────────┘
               │ triggered
               ▼
        RECORD TRADE
        Entry price, T+15, T+30,
        T+60, EOD returns
        WIN / LOSS outcome
```

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
│              │              │              │                │
│ price_       │ context_     │ run_         │                │
│ fetcher.py   │ filter.py    │ backtest.py  │                │
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
      └─ Yahoo Finance → fetch daily + 5-min price bars
             │
             ▼
         SQLite DB
         /data/matd_backtest.db
             │
             ├─ rns_events       (announcements)
             ├─ price_bars       (OHLCV, 1d + 5m)
             └─ backtest_results (signal outcomes)

ON DEMAND:
  run_backtest.py
      │
      └─ Loops all tickers × all RNS events
         Runs 3 filters, detects reactions,
         calculates returns, saves to backtest_results

ALWAYS ON (systemd service):
  run_dashboard.py → Flask on port 5001
      │
      ├─ GET /              → Summary tab
      ├─ GET /chart-data    → Price Chart tab
      ├─ GET /backtest-data → Analysis tab
      └─ GET /rns/<id>      → Drawer detail
```

---

## Tickers

12 AIM-listed oil & gas juniors:

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
| SOUC | Southern Energy Corp |
| BLOE | Block Energy plc |

---

## File map

```
rns-trader/
├── config/
│   └── settings.py            # All constants, ticker list, API keys
├── src/
│   ├── collect/
│   │   ├── database.py        # SQLite schema + connection
│   │   ├── rns_fetcher.py     # LSE API: RNS list + body fetch
│   │   ├── price_fetcher.py   # Yahoo Finance OHLCV download
│   │   └── html_cleaner.py    # Strip HTML from RNS body text
│   ├── react/
│   │   ├── category_filter.py   # Filter 1: skip/watch/high priority
│   │   ├── context_filter.py    # Filter 2: price setup quality
│   │   └── reaction_detector.py # Filter 3: volume + price spike
│   ├── backtest/
│   │   └── simulator.py       # Main backtest loop, calls all 3 filters
│   └── score/
│       ├── scorer.py          # Grok LLM scoring (optional)
│       └── prompts.py         # LLM prompt templates
├── scripts/
│   ├── run_collect.py         # Entry point: collect data
│   ├── run_backtest.py        # Entry point: run backtest
│   └── run_dashboard.py       # Entry point: start Flask
└── dashboard/
    ├── app.py                 # Flask routes + SQL queries
    └── templates/
        └── index.html         # Single-page dashboard UI
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

```bash
cp .env.example .env
# Edit .env and add your xAI API key (optional — only needed for LLM scoring)
```

### Collect data

```bash
# All tickers
python scripts/run_collect.py

# Specific tickers
python scripts/run_collect.py MATD PANR
```

### Run backtest

```bash
# All tickers
python scripts/run_backtest.py

# Single ticker
python scripts/run_backtest.py MATD

# With Grok LLM scoring
python scripts/run_backtest.py --llm
```

### Start dashboard

```bash
python scripts/run_dashboard.py
# Open http://localhost:5001
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
| id | INTEGER | LSE announcement ID |
| ticker | TEXT | Stock ticker |
| rnsnumber | TEXT | RNS reference number |
| category | TEXT | LSE category code (DRL, UPD, FR, etc.) |
| headlinename | TEXT | Human-readable category name |
| title | TEXT | Announcement title |
| datetime | TEXT | Publication datetime (ISO 8601) |
| body_text | TEXT | Full announcement text (cleaned) |
| fetch_status | TEXT | pending / ok / error / no_content |

### `price_bars`
| Column | Type | Description |
|--------|------|-------------|
| ticker | TEXT | Stock ticker |
| interval | TEXT | 1d or 5m |
| datetime | TEXT | Bar datetime (ISO 8601) |
| open/high/low/close | REAL | Price in pence |
| volume | INTEGER | Shares traded |

### `backtest_results`
| Column | Type | Description |
|--------|------|-------------|
| rns_id | INTEGER | FK → rns_events.id |
| ticker | TEXT | Stock ticker |
| category | TEXT | LSE category code |
| category_priority | TEXT | high / watch / skip |
| skipped_category | INTEGER | 1 if skipped by filter 1 |
| setup_quality | TEXT | strong / neutral / extended / skip |
| skipped_context | INTEGER | 1 if skipped by filter 2 |
| timing | TEXT | pre_market / intraday |
| reaction_triggered | INTEGER | 1 if volume+price spike detected |
| reaction_strength | REAL | Volume multiple (e.g. 6.2) |
| reaction_direction | TEXT | BUY / SELL |
| reaction_confidence | REAL | 0.0–1.0 |
| reaction_price_chg | REAL | % price change in reaction window |
| avg_vol_20d | INTEGER | 20-day average daily volume |
| immediate_vol | INTEGER | Volume in reaction window |
| bars_found | INTEGER | Number of 5-min bars found |
| entry_price | REAL | Price at trade entry (pence) |
| return_t15 | REAL | % return at T+15 min |
| return_t30 | REAL | % return at T+30 min |
| return_t60 | REAL | % return at T+60 min |
| return_eod | REAL | % return at end of day |
| outcome_t15 | TEXT | WIN / LOSS at T+15 |
| outcome_eod | TEXT | WIN / LOSS at EOD |
| would_trade | INTEGER | 1 if all filters passed |
| llm_score | INTEGER | Grok score 1–5 (optional) |
| model_used | TEXT | LLM model name (optional) |

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
| BOA | Board changes | SKIP |
| NOA | Notice of AGM | SKIP |
| RAG | Result of AGM | SKIP |
| NRA | Non-regulatory announcement | SKIP |
| AGR | Agreement | SKIP |

---

## LLM scoring (optional)

When run with `--llm`, each triggered event is scored by Grok (xAI) on a 1–5 scale:

- **5** — Transformational news, major catalyst
- **4** — Strong positive, likely sustained move
- **3** — Moderate interest, directional but uncertain
- **2** — Minor news, limited follow-through expected
- **1** — Neutral or negative, avoid

Requires `XAI_API_KEY` in `.env`.

---

## Dashboard

Accessible at `http://raspberrypi.local:5001`

| Tab | Contents |
|-----|----------|
| Summary | RNS counts, price data coverage, category breakdown, recent announcements, all-tickers overview |
| Price Chart | Interactive Plotly candlestick chart with RNS event markers, colour-coded by category |
| Backtest Analysis | Win rate by reaction strength, timing, category, setup quality. Cumulative P&L curve. Full event table |

Click any announcement row to open a detail drawer with the full RNS text and backtest result.

---

## Limitations

- **Intraday data:** Yahoo Finance only provides 60 days of 5-min bars for free. Reaction detection on events older than 60 days falls back to daily bar analysis.
- **Execution:** This is a signal detection system, not a broker integration. Trade execution is manual.
- **Survivorship bias:** Only currently-listed tickers are tracked. Delisted companies are excluded.
- **LSE API:** Uses undocumented LSE web API endpoints. Subject to change without notice.

---

## Roadmap

- [ ] Broker API integration (Interactive Brokers / Alpaca)
- [ ] Live intraday monitoring with alert notifications
- [ ] Expand ticker universe beyond oil & gas
- [ ] Alpha Vantage integration for extended intraday history
- [ ] Multi-strategy backtesting framework
