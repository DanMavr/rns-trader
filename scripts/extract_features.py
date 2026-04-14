"""
Phase 1 — Feature Extraction
=============================
Produces a flat observation table: one row per RNS event.

For each event computes:

REACTION DAY FEATURES (what the market did on the RNS day)
  - vol_ratio          : reaction_day_volume / avg_20d_volume
  - oc_pct             : (close - open) / open * 100   [open-to-close]
  - gap_pct            : (open - prev_close) / prev_close * 100  [gap at open]
  - day_range_pct      : (high - low) / open * 100     [full day range]
  - direction          : +1 if close > open, -1 if close < open

PRE-RNS CONTEXT (measured from bars BEFORE the RNS date)
  - price_position     : where price sits in 52-week range (0=low, 1=high)
  - above_sma20        : 1 if price above 20-day SMA, 0 if below
  - ret_5d             : 5-day return into the RNS
  - ret_20d            : 20-day return into the RNS
  - ret_60d            : 60-day return into the RNS
  - pre_vol_ratio      : avg_5d_vol / avg_20d_vol (accumulation signal)

EVENT METADATA
  - ticker, category, timing (pre_market/intraday/post_market)
  - rns_date, rns_id

FORWARD RETURNS (from close of reaction day)
  - fwd_1d  : next day close vs reaction day close
  - fwd_2d  : 2 days forward
  - fwd_3d  : 3 days forward
  - fwd_5d  : 5 days forward
  - fwd_10d : 10 days forward
  - fwd_15d : 15 days forward
  - fwd_20d : 20 days forward

FORWARD RETURNS (from OPEN of next day — execution-realistic)
  - fwd_nxt_open_to_1d_close : buy at next open, sell at next close
  - fwd_nxt_open_to_3d       : buy at next open, hold 3 days
  - fwd_nxt_open_to_5d       : buy at next open, hold 5 days
  - fwd_nxt_open_to_10d      : buy at next open, hold 10 days

All returns are raw (not direction-adjusted) — positive means price went up.
Direction tells you whether going long or short would have made money.

Output: data/features.csv
"""
import sqlite3
import csv
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path("data/matd_backtest.db")
OUT_PATH = Path("data/features.csv")

SKIP_CATEGORIES = {"NOA", "RAG", "BOA", "BOD", "NRA", "AGR", "HOL", "DSH"}


def get_bars(conn, ticker):
    """Return all 1d bars for a ticker as list of dicts, sorted ascending."""
    rows = conn.execute("""
        SELECT SUBSTR(datetime,1,10) as date,
               open, high, low, close, volume
        FROM price_bars
        WHERE ticker=? AND interval='1d'
        ORDER BY datetime ASC
    """, (ticker,)).fetchall()
    return [dict(r) for r in rows]


def build_date_index(bars):
    """Map date string -> index in bars list for fast lookup."""
    return {b['date']: i for i, b in enumerate(bars)}


def classify_timing(dt_str):
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z",""))
        m  = dt.hour * 60 + dt.minute
        if m < 480:   return "pre_market"
        if m > 990:   return "post_market"
        return "intraday"
    except:
        return "unknown"


def get_reaction_date(dt_str, timing):
    if timing == "post_market":
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z",""))
            nd = dt + timedelta(days=1)
            while nd.weekday() >= 5:
                nd += timedelta(days=1)
            return nd.strftime("%Y-%m-%d")
        except:
            pass
    return dt_str[:10]


def pct(a, b):
    """(a - b) / b * 100, or None if b is 0 or None."""
    if b and b != 0 and a is not None:
        return round((a - b) / b * 100, 4)
    return None


def extract_features():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    events = conn.execute("""
        SELECT id, ticker, category, datetime, title
        FROM rns_events
        WHERE fetch_status='ok'
        ORDER BY ticker, datetime ASC
    """).fetchall()
    events = [dict(e) for e in events]

    # Pre-load all bars per ticker
    tickers = list({e['ticker'] for e in events})
    all_bars  = {}
    all_idx   = {}
    for t in tickers:
        bars = get_bars(conn, t)
        all_bars[t] = bars
        all_idx[t]  = build_date_index(bars)

    conn.close()

    rows = []
    skipped = 0

    for ev in events:
        ticker   = ev['ticker']
        cat      = (ev['category'] or '').upper()
        dt_str   = ev['datetime']
        rns_id   = ev['id']
        timing   = classify_timing(dt_str)
        rxn_date = get_reaction_date(dt_str, timing)

        # Skip routine admin
        if cat in SKIP_CATEGORIES:
            skipped += 1
            continue

        bars = all_bars.get(ticker, [])
        idx  = all_idx.get(ticker, {})

        # Find reaction bar index
        ri = idx.get(rxn_date)
        if ri is None:
            skipped += 1
            continue  # No bar on reaction date

        rxn = bars[ri]

        # ── Pre-RNS context (bars BEFORE reaction date) ───────────────────
        pre = bars[:ri]  # all bars before reaction day

        if len(pre) < 5:
            skipped += 1
            continue  # insufficient history

        closes  = [b['close']  for b in reversed(pre)]  # [0]=most recent
        volumes = [b['volume'] for b in reversed(pre)]

        prev_close = closes[0]  # day before reaction day

        # Price position in 52-week range
        yr_bars  = closes[:252]
        yr_high  = max(yr_bars)
        yr_low   = min(yr_bars)
        yr_range = yr_high - yr_low
        price_pos = round((prev_close - yr_low) / yr_range, 4) \
                    if yr_range > 0 else 0.5

        # SMA20
        sma20      = sum(closes[:20]) / min(20, len(closes))
        above_sma20 = 1 if prev_close > sma20 else 0

        # Returns into RNS
        ret_5d  = pct(prev_close, closes[5])  if len(closes) > 5  else None
        ret_20d = pct(prev_close, closes[20]) if len(closes) > 20 else None
        ret_60d = pct(prev_close, closes[60]) if len(closes) > 60 else None

        # Pre-vol ratio
        avg_vol_5d  = sum(volumes[:5])  / min(5,  len(volumes))
        avg_vol_20d = sum(volumes[:20]) / min(20, len(volumes))
        pre_vol_ratio = round(avg_vol_5d / avg_vol_20d, 4) \
                        if avg_vol_20d > 0 else None

        # ── Reaction day features ─────────────────────────────────────────
        vol_ratio = round(rxn['volume'] / avg_vol_20d, 4) \
                    if avg_vol_20d > 0 else None

        oc_pct = pct(rxn['close'], rxn['open'])

        gap_pct = pct(rxn['open'], prev_close)

        day_range_pct = round((rxn['high'] - rxn['low']) / rxn['open'] * 100, 4) \
                        if rxn['open'] else None

        direction = 1 if (rxn['close'] or 0) >= (rxn['open'] or 0) else -1

        # ── Forward returns from reaction day CLOSE ───────────────────────
        def fwd_from_close(n_days):
            fi = ri + n_days
            if fi >= len(bars):
                return None
            return pct(bars[fi]['close'], rxn['close'])

        fwd_1d  = fwd_from_close(1)
        fwd_2d  = fwd_from_close(2)
        fwd_3d  = fwd_from_close(3)
        fwd_5d  = fwd_from_close(5)
        fwd_10d = fwd_from_close(10)
        fwd_15d = fwd_from_close(15)
        fwd_20d = fwd_from_close(20)

        # ── Forward returns from NEXT DAY OPEN (execution-realistic) ──────
        nxt_i = ri + 1
        nxt_open = bars[nxt_i]['open'] if nxt_i < len(bars) else None

        def fwd_from_nxt_open(n_days):
            fi = nxt_i + n_days - 1
            if fi >= len(bars) or nxt_open is None:
                return None
            return pct(bars[fi]['close'], nxt_open)

        fwd_no_1d  = fwd_from_nxt_open(1)
        fwd_no_3d  = fwd_from_nxt_open(3)
        fwd_no_5d  = fwd_from_nxt_open(5)
        fwd_no_10d = fwd_from_nxt_open(10)

        rows.append({
            # Identity
            'rns_id':           rns_id,
            'ticker':           ticker,
            'rns_date':         rxn_date,
            'category':         cat,
            'timing':           timing,
            # Reaction day
            'vol_ratio':        vol_ratio,
            'oc_pct':           oc_pct,
            'gap_pct':          gap_pct,
            'day_range_pct':    day_range_pct,
            'direction':        direction,
            'avg_vol_20d':      round(avg_vol_20d, 0),
            'rxn_volume':       rxn['volume'],
            'rxn_open':         rxn['open'],
            'rxn_close':        rxn['close'],
            # Pre-RNS context
            'price_position':   price_pos,
            'above_sma20':      above_sma20,
            'ret_5d':           ret_5d,
            'ret_20d':          ret_20d,
            'ret_60d':          ret_60d,
            'pre_vol_ratio':    pre_vol_ratio,
            # Forward from close
            'fwd_1d':           fwd_1d,
            'fwd_2d':           fwd_2d,
            'fwd_3d':           fwd_3d,
            'fwd_5d':           fwd_5d,
            'fwd_10d':          fwd_10d,
            'fwd_15d':          fwd_15d,
            'fwd_20d':          fwd_20d,
            # Forward from next open
            'fwd_no_1d':        fwd_no_1d,
            'fwd_no_3d':        fwd_no_3d,
            'fwd_no_5d':        fwd_no_5d,
            'fwd_no_10d':       fwd_no_10d,
        })

    # Write CSV
    if rows:
        fields = list(rows[0].keys())
        with open(OUT_PATH, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    print(f"Events processed : {len(rows)}")
    print(f"Events skipped   : {skipped}")
    print(f"Output           : {OUT_PATH}")
    print(f"Columns          : {len(fields) if rows else 0}")
    return rows


if __name__ == "__main__":
    rows = extract_features()
    if rows:
        import statistics
        print(f"\nSample row (first event):")
        for k, v in list(rows[0].items()):
            print(f"  {k:<20}: {v}")
