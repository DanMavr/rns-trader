from collections import Counter, defaultdict
from src.collect.database import get_connection
from config.settings import TICKER


def print_report(ticker=TICKER):
    conn = get_connection()
    results = conn.execute("""
        SELECT r.*, e.category, e.headlinename, e.title, e.datetime
        FROM backtest_results r
        JOIN rns_events e ON r.rns_id = e.id
        WHERE e.ticker = ?
        ORDER BY e.datetime ASC
    """, (ticker,)).fetchall()
    conn.close()

    if not results:
        print("No backtest results found. Run scripts/run_backtest.py first.")
        return

    all_r      = [r for r in results if r["return_t15"] is not None]
    tradeable  = [r for r in all_r   if r["would_trade"] == 1]
    wins       = [r for r in tradeable if r["outcome_t15"] == "WIN"]

    print("=" * 70)
    print(f"  BACKTEST REPORT — {ticker}")
    print("=" * 70)
    print(f"  Total events scored:         {len(results)}")
    print(f"  Events with price data:      {len(all_r)}")
    print(f"  Would-trade signals:         {len(tradeable)}")
    if tradeable:
        print(f"  Wins at T+15min:             {len(wins)}")
        print(f"  Win rate (T+15):             {len(wins)/len(tradeable)*100:.1f}%")
        avg_ret = sum(r['return_t15'] for r in tradeable) / len(tradeable)
        print(f"  Avg return per trade T+15:   {avg_ret:+.2f}%")

    # Score distribution
    print(f"\n  SCORE DISTRIBUTION")
    print(f"  {'─'*40}")
    for score in range(2, -3, -1):
        n = sum(1 for r in results if r['llm_score'] == score)
        bar = "█" * n
        print(f"  {score:+d}  {bar:<25} ({n})")

    # By category
    print(f"\n  BY RNS CATEGORY")
    print(f"  {'─'*65}")
    print(f"  {'Cat':<6} {'N':>3}  {'AvgScore':>9}  {'AvgRet%':>9}  "
          f"{'Trades':>7}  {'WinRate':>8}")
    by_cat = defaultdict(list)
    for r in all_r:
        by_cat[r['category']].append(r)
    for cat, rows in sorted(by_cat.items()):
        avg_score = sum(r['llm_score'] for r in rows) / len(rows)
        avg_ret   = sum(r['return_t15'] for r in rows) / len(rows)
        t_rows    = [r for r in rows if r['would_trade']]
        w_rows    = [r for r in t_rows if r['outcome_t15'] == 'WIN']
        wr = f"{len(w_rows)/len(t_rows)*100:.0f}%" if t_rows else "—"
        print(f"  {cat:<6} {len(rows):>3}  {avg_score:>+9.1f}  "
              f"{avg_ret:>+9.2f}%  {len(t_rows):>7}  {wr:>8}")

    # All trade signals detail
    if tradeable:
        print(f"\n  ALL TRADE SIGNALS")
        print(f"  {'─'*70}")
        print(f"  {'Date':<12} {'Cat':<5} {'Sc':>3} {'Conf':<7} "
              f"{'Entry':>6} {'T+15':>6} {'Ret%':>7} {'Result':<6}  Title")
        for r in tradeable:
            print(f"  {r['datetime'][:10]:<12} "
                  f"{r['category']:<5} "
                  f"{r['llm_score']:>+3} "
                  f"{r['llm_confidence']:<7} "
                  f"{r['entry_price']:>6.2f} "
                  f"{str(r['price_t15'] or '?'):>6} "
                  f"{str(r['return_t15'] or '?'):>7} "
                  f"{r['outcome_t15'] or 'n/a':<6}  "
                  f"{r['title'][:35] if r['title'] else ''}")

    # Losses analysis
    losses = [r for r in tradeable if r["outcome_t15"] == "LOSS"]
    if losses:
        print(f"\n  LLM MISSES (traded but lost)")
        print(f"  {'─'*65}")
        for r in losses:
            print(f"\n  {r['datetime'][:16]}  [{r['category']}] {r['title']}")
            print(f"  Score: {r['llm_score']:+d} | Reason: {r['llm_reason']}")
            print(f"  Entry: {r['entry_price']}p → T+15: {r['price_t15']}p "
                  f"({r['return_t15']:+.2f}%)")
