"""
Step 2 — Run the backtest simulation.
Requires Ollama running: ollama serve
Run on Pi: python scripts/run_backtest.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.simulator import run_backtest
from config.settings import TICKER

if __name__ == "__main__":
    print("=" * 60)
    print(f"  RNS TRADER — Backtest — {TICKER}")
    print("  Requires Ollama: ollama serve && ollama pull llama3")
    print("=" * 60)
    run_backtest(ticker=TICKER, dry_run=False)
    print("\nNext step: python scripts/run_analyse.py")
