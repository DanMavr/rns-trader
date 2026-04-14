"""
Step 3 — Print backtest analysis report.

Usage:
  python scripts/run_analyse.py           # full multi-ticker summary
  python scripts/run_analyse.py MATD      # single ticker detail
  python scripts/run_analyse.py MATD 88E  # multiple tickers detail
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.analyser import print_summary, print_report
from config.settings import TICKERS

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    requested = [a for a in args if a in TICKERS]

    # Always print the overall summary first
    print_summary(tickers=TICKERS)

    # Then drill into specific tickers if requested
    if requested:
        for ticker in requested:
            print_report(ticker=ticker, tickers=TICKERS)
    else:
        # No specific ticker — drill into top 5 by trade count
        print("\n  (Pass a ticker symbol for per-ticker detail, e.g.)")
        print("  python scripts/run_analyse.py MATD TXP")
