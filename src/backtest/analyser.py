"""
Backtest analyser — reaction-signal results.

Works across all tickers. Uses EOD returns (daily bars only —
no 5m intraday bars collected in backtest).
"""
from collections import defaultdict
from src.collect.database import get_connection
from config.settings import TICKERS


# ── Helpers ───────────────────────────────────────────────────────────────

def _fetch_results(tickers=None):
    conn = get_connection()
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
    conn.close()
    return [dict(r) for r in rows]


def _win_rate(trades):
    wins = [t for t in trades if t["outcome_eod"] == "WIN"]
    return len(wins) / len(trades) * 100 if trades else 0.0


def _avg_return(trades):
    rets = [t["return_eod"] for t in trades if t["return_eod"] is not None]
    return sum(rets) / len(rets) if rets else 0.0


def _profit_factor(trades):
    gains  = sum(t["return_eod"] for t in trades
                 if (t["return_eod"] or 0) > 0)
    losses = abs(sum(t["return_eod"] for t in trades
                     if (t["return_eod"] or 0) < 0))
    return round(gains / losses, 2) if losses else float("inf")


# ── Multi-ticker summary ──────────────────────────────────────────────────

def print_summary(tickers=None):
    all_rows  = _fetch_results(list(tickers.keys()) if tickers else None)
    traded    = [r for r in all_rows if r["would_trade"] == 1]
    with_ret  = [r for r in traded   if r["return_eod"] is not None]

    print("\n" + "=" * 70)
    print("  BACKTEST SUMMARY — ALL TICKERS")
    print("=" * 70)
    print(f"  Total events processed : {len(all_rows)}")
    print(f"  Skipped (category)     : {sum(1 for r in all_rows if r['skipped_category'])}")
    print(f"  Skipped (context)      : {sum(1 for r in all_rows if r['skipped_context'])}")
    print(f"  No reaction            : {sum(1 for r in all_rows if not r['would_trade'] and not r['skipped_category'] and not r['skipped_context'])}")
    print(f"  Triggered trades       : {len(traded)}")
    print(f"  Trades with EOD return : {len(with_ret)}")

    if with_ret:
        wr = _win_rate(with_ret)
        ar = _avg_return(with_ret)
        pf = _profit_factor(with_ret)
        wins   = [r for r in with_ret if r["outcome_eod"] == "WIN"]
        losses = [r for r in with_ret if r["outcome_eod"] == "LOSS"]
        avg_win  = _avg_return(wins)   if wins   else 0
        avg_loss = _avg_return(losses) if losses else 0
        print(f"\n  ── EOD Exit Performance ──────────────────────────────")
        print(f"  Win rate        : {wr:.1f}%  ({len(wins)}W / {len(losses)}L)")
        print(f"  Avg return      : {ar:+.2f}%")
        print(f"  Avg win         : {avg_win:+.2f}%")
        print(f"  Avg loss        : {avg_loss:+.2f}%")
        print(f"  Profit factor   : {pf}")

    # Per-ticker table
    print(f"\n  ── By Ticker ─────────────────────────────────────────")
    print(f"  {'Ticker':<6}  {'Trades':>6}  {'W':>4}  {'L':>4}  "
          f"{'WR%':>6}  {'AvgRet%':>8}  {'PF':>6}  Name")
    print(f"  {'─'*68}")

    by_ticker = defaultdict(list)
    for r in with_ret:
        by_ticker[r["ticker"]].append(r)

    for ticker, rows in sorted(by_ticker.items(),
                                key=lambda x: -len(x[1])):
        wins   = [r for r in rows if r["outcome_eod"] == "WIN"]
        losses = [r for r in rows if r["outcome_eod"] == "LOSS"]
        wr  = _win_rate(rows)
        ar  = _avg_return(rows)
        pf  = _profit_factor(rows)
        name = (tickers or TICKERS).get(ticker, {}).get("name", "") \
               if isinstance((tickers or TICKERS).get(ticker), dict) else ""
        print(f"  {ticker:<6}  {len(rows):>6}  {len(wins):>4}  {len(losses):>4}  "
              f"{wr:>6.1f}  {ar:>+8.2f}%  {pf:>6}  {name[:35]}")


# ── Per-ticker detail ─────────────────────────────────────────────────────

def print_report(ticker, tickers=None):
    rows    = _fetch_results([ticker])
    traded  = [r for r in rows if r["would_trade"] == 1]
    with_ret = [r for r in traded if r["return_eod"] is not None]

    name = ""
    src = tickers or TICKERS
    if isinstance(src.get(ticker), dict):
        name = src[ticker].get("name", "")

    print("\n" + "=" * 70)
    print(f"  BACKTEST REPORT — {ticker}  {name}")
    print("=" * 70)
    print(f"  Total events   : {len(rows)}")
    print(f"  Skipped        : {sum(1 for r in rows if r['skipped_category'] or r['skipped_context'])}")
    print(f"  No reaction    : {sum(1 for r in rows if not r['would_trade'] and not r['skipped_category'] and not r['skipped_context'])}")
    print(f"  Triggered      : {len(traded)}")
    print(f"  With EOD data  : {len(with_ret)}")

    if not with_ret:
        print("  No trades with EOD return data.")
        return

    wr = _win_rate(with_ret)
    ar = _avg_return(with_ret)
    pf = _profit_factor(with_ret)
    wins   = [r for r in with_ret if r["outcome_eod"] == "WIN"]
    losses = [r for r in with_ret if r["outcome_eod"] == "LOSS"]

    print(f"\n  ── EOD Performance ───────────────────────────────────")
    print(f"  Win rate      : {wr:.1f}%  ({len(wins)}W / {len(losses)}L)")
    print(f"  Avg return    : {ar:+.2f}%")
    print(f"  Avg win       : {_avg_return(wins):+.2f}%")
    print(f"  Avg loss      : {_avg_return(losses):+.2f}%")
    print(f"  Profit factor : {pf}")

    # By category
    print(f"\n  ── By Category ───────────────────────────────────────")
    print(f"  {'Cat':<6}  {'N':>3}  {'W':>3}  {'L':>3}  {'WR%':>6}  {'AvgRet%':>9}")
    by_cat = defaultdict(list)
    for r in with_ret:
        by_cat[r["category"]].append(r)
    for cat, cat_rows in sorted(by_cat.items()):
        w = [r for r in cat_rows if r["outcome_eod"] == "WIN"]
        l = [r for r in cat_rows if r["outcome_eod"] == "LOSS"]
        print(f"  {cat:<6}  {len(cat_rows):>3}  {len(w):>3}  {len(l):>3}  "
              f"{_win_rate(cat_rows):>6.1f}  {_avg_return(cat_rows):>+9.2f}%")

    # By timing
    print(f"\n  ── By Timing ─────────────────────────────────────────")
    by_timing = defaultdict(list)
    for r in with_ret:
        by_timing[r["timing"]].append(r)
    for t, t_rows in sorted(by_timing.items()):
        w = [r for r in t_rows if r["outcome_eod"] == "WIN"]
        print(f"  {t:<12}  {len(t_rows):>3} trades  "
              f"WR: {_win_rate(t_rows):.1f}%  "
              f"Avg: {_avg_return(t_rows):+.2f}%")

    # Trade detail
    print(f"\n  ── All Trades ────────────────────────────────────────")
    print(f"  {'Date':<11} {'Cat':<5} {'Dir':<4} {'Str':>5}  "
          f"{'Entry':>7}  {'EOD':>7}  {'Ret%':>7}  {'Out':<5}  Title")
    print(f"  {'─'*70}")
    for r in with_ret:
        print(f"  {r['rns_datetime'][:10]:<11} "
              f"{r['category']:<5} "
              f"{r['direction']:<4} "
              f"{r['reaction_strength']:>5.1f}×  "
              f"{r['entry_price']:>7.2f}  "
              f"{r['price_eod']:>7.2f}  "
              f"{r['return_eod']:>+7.2f}%  "
              f"{r['outcome_eod']:<5}  "
              f"{(r['title'] or '')[:35]}")
