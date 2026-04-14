"""
Backtest analyser — reaction-signal results.

Entry: next trading day open after reaction (no same-bar bias).
Exits: T+1d close, T+5d close, T+20d close.
"""
from collections import defaultdict
from src.collect.database import get_connection
from config.settings import TICKERS


# ── Helpers ───────────────────────────────────────────────────────────────

def _fetch_results(tickers=None):
    conn = get_connection()
    try:
        if tickers:
            placeholders = ",".join("?" * len(tickers))
            rows = conn.execute(f"""
                SELECT r.*, e.title, e.datetime as rns_datetime
                FROM backtest_results r
                JOIN rns_events e ON r.rns_id = e.id
                WHERE r.ticker IN ({placeholders})
                ORDER BY r.ticker, e.datetime ASC
            """, list(tickers)).fetchall()
        else:
            rows = conn.execute("""
                SELECT r.*, e.title, e.datetime as rns_datetime
                FROM backtest_results r
                JOIN rns_events e ON r.rns_id = e.id
                ORDER BY r.ticker, e.datetime ASC
            """).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def _win_rate(trades, col="outcome_t5d"):
    wins = [t for t in trades if t[col] == "WIN"]
    return len(wins) / len(trades) * 100 if trades else 0.0


def _avg_return(trades, col="return_t5d"):
    rets = [t[col] for t in trades if t[col] is not None]
    return sum(rets) / len(rets) if rets else 0.0


def _profit_factor(trades, col="return_t5d"):
    gains  = sum(t[col] for t in trades if (t[col] or 0) > 0)
    losses = abs(sum(t[col] for t in trades if (t[col] or 0) < 0))
    return round(gains / losses, 2) if losses else float("inf")


def _outcome_counts(trades, col="outcome_t5d"):
    wins   = [t for t in trades if t[col] == "WIN"]
    losses = [t for t in trades if t[col] == "LOSS"]
    return len(wins), len(losses)


# ── Multi-ticker summary ──────────────────────────────────────────────────

def print_summary(tickers=None):
    all_rows = _fetch_results(list(tickers.keys()) if tickers else None)
    traded   = [r for r in all_rows if r["would_trade"] == 1]

    with_t1  = [r for r in traded if r["return_t1d"]  is not None]
    with_t5  = [r for r in traded if r["return_t5d"]  is not None]
    with_t20 = [r for r in traded if r["return_t20d"] is not None]

    print("\n" + "=" * 70)
    print("  BACKTEST SUMMARY — ALL TICKERS")
    print("=" * 70)
    print(f"  Total events processed : {len(all_rows)}")
    print(f"  Skipped (category)     : {sum(1 for r in all_rows if r['skipped_category'])}")
    print(f"  Skipped (context)      : {sum(1 for r in all_rows if r['skipped_context'])}")
    print(f"  No reaction            : {sum(1 for r in all_rows if not r['would_trade'] and not r['skipped_category'] and not r['skipped_context'])}")
    print(f"  Triggered trades       : {len(traded)}")

    for label, subset, col_r, col_o in [
        ("T+1d  (next day close)  ", with_t1,  "return_t1d",  "outcome_t1d"),
        ("T+5d  (5 days close)   ",  with_t5,  "return_t5d",  "outcome_t5d"),
        ("T+20d (20 days close)  ",  with_t20, "return_t20d", "outcome_t20d"),
    ]:
        if not subset:
            continue
        w, l  = _outcome_counts(subset, col_o)
        wr    = _win_rate(subset, col_o)
        ar    = _avg_return(subset, col_r)
        pf    = _profit_factor(subset, col_r)
        avg_w = _avg_return([t for t in subset if t[col_o] == "WIN"],  col_r)
        avg_l = _avg_return([t for t in subset if t[col_o] == "LOSS"], col_r)
        print(f"\n  -- {label} -------------------")
        print(f"  Trades      : {len(subset)}")
        print(f"  Win rate    : {wr:.1f}%  ({w}W / {l}L)")
        print(f"  Avg return  : {ar:+.2f}%")
        print(f"  Avg win     : {avg_w:+.2f}%")
        print(f"  Avg loss    : {avg_l:+.2f}%")
        print(f"  Prof factor : {pf}")

    # Per-ticker table sorted by avg T+5d return
    print(f"\n  -- By Ticker (T+5d) " + "-"*49)
    print(f"  {'Ticker':<6}  {'Trades':>6}  {'W':>4}  {'L':>4}  "
          f"{'WR%':>6}  {'AvgRet%':>8}  {'PF':>6}  Name")
    print(f"  {'─'*68}")

    by_ticker = defaultdict(list)
    for r in with_t5:
        by_ticker[r["ticker"]].append(r)

    for ticker, rows in sorted(by_ticker.items(),
                                key=lambda x: -_avg_return(x[1], "return_t5d")):
        w, l = _outcome_counts(rows, "outcome_t5d")
        wr   = _win_rate(rows,       "outcome_t5d")
        ar   = _avg_return(rows,     "return_t5d")
        pf   = _profit_factor(rows,  "return_t5d")
        t_data = tickers or TICKERS
        name = t_data.get(ticker, {}).get("name", "") \
               if isinstance(t_data.get(ticker), dict) else ""
        print(f"  {ticker:<6}  {len(rows):>6}  {w:>4}  {l:>4}  "
              f"{wr:>6.1f}  {ar:>+8.2f}%  {pf:>6}  {name[:35]}")


# ── Per-ticker detail ─────────────────────────────────────────────────────

def print_report(ticker, tickers=None):
    rows     = _fetch_results([ticker])
    traded   = [r for r in rows if r["would_trade"] == 1]
    with_t1  = [r for r in traded if r["return_t1d"]  is not None]
    with_t5  = [r for r in traded if r["return_t5d"]  is not None]
    with_t20 = [r for r in traded if r["return_t20d"] is not None]

    t_data = tickers or TICKERS
    name = t_data.get(ticker, {}).get("name", "") \
           if isinstance(t_data.get(ticker), dict) else ""

    print("\n" + "=" * 70)
    print(f"  BACKTEST REPORT -- {ticker}  {name}")
    print("=" * 70)
    print(f"  Total events   : {len(rows)}")
    print(f"  Skipped        : {sum(1 for r in rows if r['skipped_category'] or r['skipped_context'])}")
    print(f"  No reaction    : {sum(1 for r in rows if not r['would_trade'] and not r['skipped_category'] and not r['skipped_context'])}")
    print(f"  Triggered      : {len(traded)}")

    if not with_t5:
        print("  No trades with T+5d return data.")
        return

    print()
    for label, subset, col_r, col_o in [
        ("T+1d ",  with_t1,  "return_t1d",  "outcome_t1d"),
        ("T+5d ",  with_t5,  "return_t5d",  "outcome_t5d"),
        ("T+20d",  with_t20, "return_t20d", "outcome_t20d"),
    ]:
        if not subset:
            continue
        w, l = _outcome_counts(subset, col_o)
        wr   = _win_rate(subset,       col_o)
        ar   = _avg_return(subset,     col_r)
        pf   = _profit_factor(subset,  col_r)
        print(f"  {label}  WR: {wr:.1f}% ({w}W/{l}L)  "
              f"Avg: {ar:+.2f}%  PF: {pf}")

    # By category
    print(f"\n  -- By Category (T+5d) " + "-"*47)
    print(f"  {'Cat':<6}  {'N':>3}  {'W':>3}  {'L':>3}  {'WR%':>6}  {'AvgRet%':>9}")
    by_cat = defaultdict(list)
    for r in with_t5:
        by_cat[r["category"]].append(r)
    for cat, cat_rows in sorted(by_cat.items()):
        w, l = _outcome_counts(cat_rows, "outcome_t5d")
        print(f"  {cat:<6}  {len(cat_rows):>3}  {w:>3}  {l:>3}  "
              f"{_win_rate(cat_rows, 'outcome_t5d'):>6.1f}  "
              f"{_avg_return(cat_rows, 'return_t5d'):>+9.2f}%")

    # By timing
    print(f"\n  -- By Timing (T+5d) " + "-"*49)
    by_timing = defaultdict(list)
    for r in with_t5:
        by_timing[r["timing"]].append(r)
    for t, t_rows in sorted(by_timing.items()):
        w, l = _outcome_counts(t_rows, "outcome_t5d")
        print(f"  {t:<12}  {len(t_rows):>3} trades  "
              f"WR: {_win_rate(t_rows, 'outcome_t5d'):.1f}%  "
              f"Avg: {_avg_return(t_rows, 'return_t5d'):+.2f}%")

    # By signal strength bucket
    print(f"\n  -- By Signal Strength (T+5d) " + "-"*40)
    buckets = [(3, 5, "3-5x"), (5, 8, "5-8x"), (8, 15, "8-15x"), (15, 999, "15x+")]
    for lo, hi, label in buckets:
        bucket = [r for r in with_t5
                  if r["reaction_strength"] and lo <= r["reaction_strength"] < hi]
        if not bucket:
            continue
        w, l = _outcome_counts(bucket, "outcome_t5d")
        print(f"  {label:<6}  {len(bucket):>3} trades  "
              f"WR: {_win_rate(bucket, 'outcome_t5d'):.1f}%  "
              f"Avg: {_avg_return(bucket, 'return_t5d'):+.2f}%")

    # All trades detail
    print(f"\n  -- All Trades " + "-"*55)
    print(f"  {'React':<11} {'Entry':<11} {'Cat':<5} {'Dir':<4} "
          f"{'Str':>5}  {'Entry$':>7}  "
          f"{'T+1d':>7}  {'T+5d':>7}  {'T+20d':>7}  Title")
    print(f"  {'─'*85}")
    for r in with_t5:
        t1  = f"{r['return_t1d']:>+.1f}%"  if r["return_t1d"]  is not None else "    -"
        t5  = f"{r['return_t5d']:>+.1f}%"  if r["return_t5d"]  is not None else "    -"
        t20 = f"{r['return_t20d']:>+.1f}%" if r["return_t20d"] is not None else "    -"
        print(f"  {(r['reaction_date'] or r['rns_datetime'])[:10]:<11} "
              f"{(r['entry_time'] or '')[:10]:<11} "
              f"{r['category']:<5} "
              f"{r['direction']:<4} "
              f"{r['reaction_strength']:>5.1f}x  "
              f"{r['entry_price']:>7.2f}  "
              f"{t1:>7}  {t5:>7}  {t20:>7}  "
              f"{(r['title'] or '')[:30]}")
