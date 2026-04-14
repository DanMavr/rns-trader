"""
Utility: drop and recreate the backtest_results table.

Run this ONCE before re-running the backtest after the schema change
(old table has price_t5/t15/t30/t60/eod columns, new has price_t1d/t5d/t20d).

Usage:
  python scripts/reset_backtest_db.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.collect.database import get_connection, init_db

if __name__ == "__main__":
    conn = get_connection()
    conn.execute("DROP TABLE IF EXISTS backtest_results")
    conn.commit()
    conn.close()
    print("  backtest_results table dropped.")
    init_db()
    print("  backtest_results table recreated with new schema.")
    print("  Now run: python scripts/run_backtest.py --fresh")
