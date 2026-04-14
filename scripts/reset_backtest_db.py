"""
Hard reset: drops backtest_results, recreates with new schema, verifies columns.
Run BEFORE re-running the backtest.
"""
import sys
import sqlite3
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import DB_PATH
from src.collect.database import get_connection, init_db

if __name__ == "__main__":
    print(f"  DB path: {DB_PATH}")

    conn = get_connection()

    # Show current columns
    cols = conn.execute("PRAGMA table_info(backtest_results)").fetchall()
    print(f"\n  Current backtest_results columns ({len(cols)}):")
    for c in cols:
        print(f"    {c[1]}")

    # Drop it
    conn.execute("DROP TABLE IF EXISTS backtest_results")
    conn.commit()
    conn.close()
    print("\n  Table dropped.")

    # Recreate
    init_db()

    # Verify new columns
    conn2 = get_connection()
    new_cols = conn2.execute("PRAGMA table_info(backtest_results)").fetchall()
    conn2.close()
    print(f"\n  New backtest_results columns ({len(new_cols)}):")
    for c in new_cols:
        print(f"    {c[1]}")

    # Check key new columns exist
    col_names = [c[1] for c in new_cols]
    for expected in ["price_t1d", "price_t5d", "price_t20d",
                     "return_t1d", "return_t5d", "return_t20d",
                     "outcome_t1d", "outcome_t5d", "outcome_t20d",
                     "reaction_date"]:
        status = "OK" if expected in col_names else "MISSING!"
        print(f"    {expected}: {status}")

    # Check OLD columns are gone
    for old in ["price_t5", "price_t15", "price_eod", "return_eod", "outcome_eod"]:
        status = "STILL PRESENT - problem!" if old in col_names else "gone (good)"
        print(f"    {old}: {status}")

    print("\n  Reset complete. Now run:")
    print("  python scripts/run_backtest.py")
