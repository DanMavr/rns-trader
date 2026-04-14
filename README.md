# RNS Trader

A data-driven trading signal research platform for AIM-listed oil & gas companies, built on the London Stock Exchange RNS (Regulatory News Service) feed.

---

## What it does

Collects every regulatory announcement (RNS) for a universe of 32 AIM-listed oil & gas companies, pairs each announcement with daily OHLCV price data, and builds a flat feature table that enables assumption-free statistical analysis of what actually predicts forward returns — and what doesn't.

The goal is to find the top ~10% of RNS events that produce meaningful, statistically supported forward price moves, derive trading rules entirely from the data, and validate them out-of-sample before any live use.

---

## Methodology

### Principle: data first, assumptions never

Every threshold, every filter, every rule must be derived from the data — not assumed. The workflow enforces this with a strict 4-phase process:

```
Phase 1 — Ingest
  Collect RNS events + daily price bars for all 32 tickers
  Extract one feature row per event: reaction metrics, pre-RNS
  context, and forward returns at every horizon (D+1 through D+20)
  No filtering. No thresholds. Raw observations only.

Phase 2 — Explore
  Analyse distributions across every measurable factor
  Factor-by-factor decile analysis vs forward returns
  Identify which factors separate good outcomes from noise
  Require t-stat > 2.0 and n > 20 before drawing any conclusion

Phase 3 — Validate
  Apply only the rules the data itself suggested
  Strict in-sample / out-of-sample time split
  2024 = discovery period, 2025-2026 = validation period
  Rules are fixed at end of discovery — no adjustments allowed

Phase 4 — Expand
  Add more same-sector tickers to increase sample size
  Re-validate with larger dataset
  Only proceed to live use once out-of-sample T > 2.0
```

### What the data showed (April 2026, 11 tickers, 675 events)

**Base rate:** RNS events alone predict nothing. Mean forward return ~0% at every horizon. Win rate 31-40%. The null hypothesis holds for the general population.

**The one real signal:** Volume ratio (reaction day volume / 20-day average volume). The top decile (>4.5× average) shows consistent positive forward drift:
- D+2: +2.7% mean, T=2.04 ✅
- D+3: +3.1% mean, T=2.15 ✅
- D+5: +4.0% mean, T=1.87

**Direction matters:** High volume + stock closes UP on RNS day → +6.9% from next open over 5 days. High volume + closes DOWN → only +0.8%.

**Categories:** UPD (operational updates) produce no edge even with high volume. DRL (drilling results) + high volume = T=2.52 but only 4 events — directionally confirmed, insufficient sample.

**Optimal hold:** 3-5 trading days from next day's open.

**Out-of-sample (2025-2026):** 11 trades, 72.7% win rate at D+10, mean +5.5%. Signal did not degrade.

**Honest constraint:** 19 total qualifying trades across 2 years × 11 tickers is too small for definitive conclusions. T-stats are 1.75-1.94 — approaching but not at 2.0. The expansion to 32 tickers is intended to resolve this.

---

## Data quality notes

- **88E stock consolidation (May 2025):** Yahoo Finance did not adjust the historical series. A 1-day forward return of +1796% was identified and removed. Any forward return window crossing a known price discontinuity is set to NULL.
- **Duplicate RNS dates:** Multiple announcements on the same day map to the same price bar. Deduplicated by keeping the highest-priority category per ticker per date.
- **Zero-volume bars:** Ghost bars (vol=0) from split/consolidation days are removed.

---

## Architecture

```
rns-trader/
├── config/
│   └── settings.py          # 32 verified tickers with LSE slugs
│
├── scripts/
│   ├── run_collect.py        # Collect RNS + prices for all tickers
│   ├── extract_features.py   # Build feature table (Phase 1)
│   └── run_backtest.py       # Rule-based backtest (Phase 3)
│
├── src/
│   ├── collect/
│   │   ├── database.py       # SQLite schema + connection
│   │   ├── rns_fetcher.py    # LSE API → rns_events table
│   │   └── price_fetcher.py  # Yahoo Finance → price_bars table
│   │
│   ├── react/
│   │   ├── category_filter.py   # Skip routine admin categories
│   │   ├── context_filter.py    # Pre-RNS price/volume context
│   │   └── reaction_detector.py # Daily bar signal detection
│   │
│   └── backtest/
│       └── simulator.py      # Applies rules, records results
│
└── data/
    ├── matd_backtest.db      # SQLite database
    ├── features.csv          # Raw feature table (Phase 1 output)
    └── features_clean.csv    # Cleaned (discontinuities + dupes removed)
```

---

## Database schema

### `rns_events`
One row per RNS announcement. Fetched from the LSE API.

| Column | Description |
|---|---|
| id | LSE announcement ID |
| ticker | Stock ticker |
| datetime | Publication timestamp |
| category | LSE category code (DRL, UPD, MSC, FR, etc.) |
| title | Headline |
| body_text | Full announcement text |
| fetch_status | `ok` / `error` |

### `price_bars`
Daily OHLCV bars from Yahoo Finance (2 years history).

| Column | Description |
|---|---|
| ticker | Stock ticker |
| datetime | Bar date |
| interval | Always `1d` |
| open / high / low / close | Prices in GBX (pence) |
| volume | Shares traded |

### `backtest_results`
One row per evaluated RNS event.

| Column | Description |
|---|---|
| reaction_triggered | 1 if signal fired |
| reaction_strength | volume / avg_vol_20d |
| price_change_pct | (close - open) / open % |
| would_trade | 1 if all filters passed |
| return_eod | EOD return on reaction day |
| outcome_eod | WIN / LOSS |

---

## Setup

```bash
git clone https://github.com/DanMavr/rns-trader
cd rns-trader
pip install -r requirements.txt

# Collect data for all 32 tickers (~30-40 minutes)
python scripts/run_collect.py

# Extract feature table
python scripts/extract_features.py

# Run backtest
python scripts/run_backtest.py
```

---

## Ticker universe

32 AIM-listed oil & gas companies. All LSE slugs verified from live URLs (April 2026).

**Original 11:** MATD, 88E, CHAR, PTAL, UJO, ZEN, BOR, AXL, PANR, KIST, BLOE

**Tier 1 additions (£20m-£750m market cap):**
RKH, ECO, AET, FOG, SEI, SAVE, JSE, ZPHR, SEA, JOG, TXP, PMG, STAR

**Tier 2 additions (£8m-£55m market cap, smaller/less liquid):**
ENW, CASP, PXEN, EOG, ORCA, EPP, SOU, UOG

---

## Current status

| Metric | Value |
|---|---|
| Tickers | 32 |
| RNS events (11 tickers) | 1,003 |
| Feature rows (clean) | 675 |
| Qualifying trades (Phase 3 rules) | 19 |
| Out-of-sample win rate (D+10) | 72.7% |
| Out-of-sample T-stat (D+10) | 1.46 |
| Combined T-stat (D+3) | 1.79 |
| Statistical significance | Not yet (target T > 2.0) |
| Next milestone | Re-run analysis with 32 tickers |

---

## What this is not

- Not a live trading system
- Not financial advice
- Not a black box — every rule has a documented data source
- Not complete — sample size is the current binding constraint

The signal is directionally real but statistically unproven at current sample size. The purpose of the 32-ticker expansion is to resolve that.
