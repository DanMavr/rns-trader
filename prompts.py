"""
Step 3 — Print the analysis report.
Run on Pi: python scripts/run_analyse.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.analyser import print_report
from config.settings import TICKER

if __name__ == "__main__":
    print_report(ticker=TICKER)
