"""
Step 3 — Print backtest analysis report.

Usage:
  python scripts/run_analyse.py           # full multi-ticker summary
  python scripts/run_analyse.py MATD      # single ticker detail
  python scripts/run_analyse.py MATD TXP  # multiple tickers detail
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.analyser import print_summary, print_report
from config.settings import TICKERS

if __name__ == "__main__":
    args      = [a for a in sys.argv[1:] if not a.startswith("--")]
    requested = [a for a in args if a in TICKERS]

    print_summary(tickers=TICKERS)

    if requested:
        for ticker in requested:
            print_report(ticker=ticker, tickers=TICKERS)
    else:
        print("\n  Tip: pass ticker symbol(s) for per-ticker detail:")
        print("  python scripts/run_analyse.py MATD TXP")
