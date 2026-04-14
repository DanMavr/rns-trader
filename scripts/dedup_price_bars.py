"""
Deduplicates price_bars table for 1d interval.

Root cause: yfinance returns daily bars with timezone-aware timestamps
that vary (e.g. 00:00:00 vs 08:00:00 UTC), causing the UNIQUE constraint
on (ticker, interval, datetime) to miss duplicates.

Fix: normalise all 1d datetime values to YYYY-MM-DD (date only),
then delete duplicates keeping the row with the highest id.

Safe to run multiple times.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.collect.database import get_connection

if __name__ == "__main__":
    conn = get_connection()

    # Step 1: normalise all 1d datetimes to YYYY-MM-DD
    updated = conn.execute("""
        UPDATE price_bars
        SET datetime = SUBSTR(datetime, 1, 10)
        WHERE interval = '1d'
          AND LENGTH(datetime) > 10
    """).rowcount
    conn.commit()
    print(f"  Normalised {updated} datetime values to YYYY-MM-DD")

    # Step 2: delete duplicates - keep highest id for each (ticker, interval, date)
    deleted = conn.execute("""
        DELETE FROM price_bars
        WHERE interval = '1d'
          AND id NOT IN (
              SELECT MAX(id)
              FROM price_bars
              WHERE interval = '1d'
              GROUP BY ticker, interval, SUBSTR(datetime, 1, 10)
          )
    """).rowcount
    conn.commit()
    print(f"  Deleted {deleted} duplicate 1d bars")

    # Step 3: verify
    tickers = conn.execute("""
        SELECT ticker,
               COUNT(*) as total,
               COUNT(DISTINCT SUBSTR(datetime,1,10)) as distinct_dates
        FROM price_bars
        WHERE interval = '1d'
        GROUP BY ticker
        ORDER BY ticker
    """).fetchall()

    print(f"\n  {'Ticker':<8} {'Total':>6} {'Distinct':>9} {'Dupes':>6}")
    print(f"  {'─'*35}")
    any_dupes = False
    for r in tickers:
        dupes = r[1] - r[2]
        flag = " ← STILL HAS DUPES" if dupes > 0 else ""
        if dupes > 0:
            any_dupes = True
        print(f"  {r[0]:<8} {r[1]:>6} {r[2]:>9} {dupes:>6}{flag}")

    if any_dupes:
        print("\n  WARNING: some tickers still have duplicates!")
    else:
        print("\n  All tickers clean.")

    conn.close()
