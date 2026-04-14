"""
Phase 1 — Feature Extraction
=============================
Produces a flat observation table: one row per non-routine RNS event.

Run:  python scripts/extract_features.py
Out:  data/features.csv   (raw, uncleaned)

Cleaning (discontinuity removal + deduplication) is done separately.
"""
import sqlite3
import csv
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH  = Path("data/matd_backtest.db")
OUT_PATH = Path("data/features.csv")

SKIP_CATEGORIES = {"NOA", "RAG", "BOA", "BOD", "NRA", "AGR", "HOL", "DSH"}


def get_bars(conn, ticker):
    rows = conn.execute("""
        SELECT SUBSTR(datetime,1,10) as date, open, high, low, close, volume
        FROM price_bars
        WHERE ticker=? AND interval='1d'
        ORDER BY datetime ASC
    """, (ticker,)).fetchall()
    return [dict(r) for r in rows]


def build_date_index(bars):
    return {b['date']: i for i, b in enumerate(bars)}


def classify_timing(dt_str):
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", ""))
        m  = dt.hour * 60 + dt.minute
        if m < 480:  return "pre_market"
        if m > 990:  return "post_market"
        return "intraday"
    except:
        return "unknown"


def get_reaction_date(dt_str, timing):
    if timing == "post_market":
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", ""))
            nd = dt + timedelta(days=1)
            while nd.weekday() >= 5:
                nd += timedelta(days=1)
            return nd.strftime("%Y-%m-%d")
        except:
            pass
    return dt_str[:10]


def pct(a, b):
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

    tickers  = list({e['ticker'] for e in events})
    all_bars = {}
    all_idx  = {}
    for t in tickers:
        bars = get_bars(conn, t)
        all_bars[t] = bars
        all_idx[t]  = build_date_index(bars)
    conn.close()

    rows    = []
    skipped = 0

    for ev in events:
        ticker   = ev['ticker']
        cat      = (ev['category'] or '').upper()
        dt_str   = ev['datetime']
        rns_id   = ev['id']
        timing   = classify_timing(dt_str)
        rxn_date = get_reaction_date(dt_str, timing)

        if cat in SKIP_CATEGORIES:
            skipped += 1
            continue

        bars = all_bars.get(ticker, [])
        idx  = all_idx.get(ticker, {})
        ri   = idx.get(rxn_date)

        if ri is None:
            skipped += 1
            continue

        rxn = bars[ri]
        pre = bars[:ri]

        if len(pre) < 5:
            skipped += 1
            continue

        closes  = [b['close']  for b in reversed(pre)]
        volumes = [b['volume'] for b in reversed(pre)]
        prev_close = closes[0]

        yr_bars   = closes[:252]
        yr_high   = max(yr_bars)
        yr_low    = min(yr_bars)
        yr_range  = yr_high - yr_low
        price_pos = round((prev_close - yr_low) / yr_range, 4) \
                    if yr_range > 0 else 0.5

        sma20       = sum(closes[:20]) / min(20, len(closes))
        above_sma20 = 1 if prev_close > sma20 else 0

        ret_5d  = pct(prev_close, closes[5])  if len(closes) > 5  else None
        ret_20d = pct(prev_close, closes[20]) if len(closes) > 20 else None
        ret_60d = pct(prev_close, closes[60]) if len(closes) > 60 else None

        avg_vol_5d    = sum(volumes[:5])  / min(5,  len(volumes))
        avg_vol_20d   = sum(volumes[:20]) / min(20, len(volumes))
        pre_vol_ratio = round(avg_vol_5d / avg_vol_20d, 4) \
                        if avg_vol_20d > 0 else None

        vol_ratio     = round(rxn['volume'] / avg_vol_20d, 4) \
                        if avg_vol_20d > 0 else None
        oc_pct        = pct(rxn['close'], rxn['open'])
        gap_pct       = pct(rxn['open'], prev_close)
        day_range_pct = round((rxn['high'] - rxn['low']) / rxn['open'] * 100, 4) \
                        if rxn['open'] else None
        direction     = 1 if (rxn['close'] or 0) >= (rxn['open'] or 0) else -1

        def fwd_close(n):
            fi = ri + n
            return pct(bars[fi]['close'], rxn['close']) if fi < len(bars) else None

        nxt_i    = ri + 1
        nxt_open = bars[nxt_i]['open'] if nxt_i < len(bars) else None

        def fwd_nxt(n):
            fi = nxt_i + n - 1
            if fi >= len(bars) or nxt_open is None:
                return None
            return pct(bars[fi]['close'], nxt_open)

        rows.append({
            'rns_id': rns_id, 'ticker': ticker, 'rns_date': rxn_date,
            'category': cat, 'timing': timing,
            'vol_ratio': vol_ratio, 'oc_pct': oc_pct, 'gap_pct': gap_pct,
            'day_range_pct': day_range_pct, 'direction': direction,
            'avg_vol_20d': round(avg_vol_20d, 0), 'rxn_volume': rxn['volume'],
            'rxn_open': rxn['open'], 'rxn_close': rxn['close'],
            'price_position': price_pos, 'above_sma20': above_sma20,
            'ret_5d': ret_5d, 'ret_20d': ret_20d, 'ret_60d': ret_60d,
            'pre_vol_ratio': pre_vol_ratio,
            'fwd_1d': fwd_close(1), 'fwd_2d': fwd_close(2),
            'fwd_3d': fwd_close(3), 'fwd_5d': fwd_close(5),
            'fwd_10d': fwd_close(10), 'fwd_15d': fwd_close(15),
            'fwd_20d': fwd_close(20),
            'fwd_no_1d': fwd_nxt(1), 'fwd_no_3d': fwd_nxt(3),
            'fwd_no_5d': fwd_nxt(5), 'fwd_no_10d': fwd_nxt(10),
        })

    if rows:
        fields = list(rows[0].keys())
        with open(OUT_PATH, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    print(f"Events processed : {len(rows)}")
    print(f"Events skipped   : {skipped}")
    print(f"Output           : {OUT_PATH}")
    print(f"Columns          : {len(rows[0]) if rows else 0}")
    return rows


if __name__ == "__main__":
    rows = extract_features()
    if rows:
        print(f"\nSample row (first event):")
        for k, v in list(rows[0].items()):
            print(f"  {k:<20}: {v}")
