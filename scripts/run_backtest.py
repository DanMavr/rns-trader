"""
Multi-ticker reaction-based backtest.

Usage:
  python scripts/run_backtest.py              # all tickers
  python scripts/run_backtest.py MATD         # single ticker
  python scripts/run_backtest.py MATD PANR    # specific tickers
  python scripts/run_backtest.py --llm        # all + Grok
  python scripts/run_backtest.py --fresh      # wipe results and re-run
"""
import sys
import traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.collect.database   import init_db, get_connection
from src.backtest.simulator import run_backtest
from config.settings import TICKERS, DEFAULT_TICKER


if __name__ == "__main__":
    use_llm   = "--llm"   in sys.argv
    use_fresh = "--fresh" in sys.argv
    args      = [a for a in sys.argv[1:] if not a.startswith("--")]
    requested = [a for a in args if a in TICKERS]

    tickers_to_run = {t: TICKERS[t] for t in requested} if requested else TICKERS

    print("=" * 60)
    print(f"  RNS TRADER — Reaction Backtest")
    print(f"  Tickers: {list(tickers_to_run.keys())}")
    print(f"  LLM:     {'Grok (parallel)' if use_llm else 'Off'}")
    print("=" * 60)

    init_db()

    if use_fresh:
        conn = get_connection()
        placeholders = ",".join("?" * len(tickers_to_run))
        deleted = conn.execute(
            f"DELETE FROM backtest_results WHERE ticker IN ({placeholders})",
            list(tickers_to_run.keys())
        ).rowcount
        conn.commit()
        conn.close()
        print(f"  --fresh: cleared {deleted} existing rows for {list(tickers_to_run.keys())}\n")

    results = {}
    for ticker in tickers_to_run:
        try:
            results[ticker] = run_backtest(ticker=ticker, use_llm=use_llm)
        except Exception as e:
            print(f"  ERROR on {ticker}: {e}")
            traceback.print_exc()
            results[ticker] = 0

    print("\n" + "=" * 60)
    print(f"  SUMMARY")
    print("=" * 60)
    for ticker, traded in results.items():
        name = TICKERS[ticker]["name"]
        print(f"  {ticker:<6}  {name:<40}  {traded} trades")
    print(f"  Total: {sum(results.values())} trades triggered")
    print("=" * 60)
