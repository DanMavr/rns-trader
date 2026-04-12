"""
Run the reaction-based backtest.
Usage:
  python scripts/run_backtest.py          # pure reaction, no LLM
  python scripts/run_backtest.py --llm    # reaction + Grok in parallel
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.collect.database import init_db
from src.backtest.simulator import run_backtest
from config.settings import TICKER

if __name__ == "__main__":
    use_llm = "--llm" in sys.argv

    print("=" * 60)
    print(f"  RNS TRADER — Reaction Backtest — {TICKER}")
    print(f"  Signal:  Volume spike + Price move")
    print(f"  LLM:     {'Grok (parallel)' if use_llm else 'Off'}")
    print("=" * 60)

    init_db()
    run_backtest(ticker=TICKER, use_llm=use_llm)

    print("\nNext: reload http://raspberrypi.local:5001")
