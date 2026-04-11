"""
Step 1 — Collect all data for the backtest.
Run on Pi:  python scripts/run_collect.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.collect.database import init_db
from src.collect.rns_fetcher import fetch_rns_list, save_rns_list, enrich_rns_bodies
from src.collect.price_fetcher import fetch_and_save_prices
from config.settings import TICKER, ISSUER_NAME

if __name__ == "__main__":
    print("=" * 60)
    print(f"  RNS TRADER — Data Collection — {TICKER}")
    print("=" * 60)

    print("\n[1/4] Initialising database...")
    init_db()

    print(f"\n[2/4] Fetching RNS list for {TICKER}...")
    items = fetch_rns_list(ticker=TICKER, issuer_name=ISSUER_NAME)
    print(f"  Found {len(items)} announcements total")
    save_rns_list(items, ticker=TICKER)

    print(f"\n[3/4] Fetching full body text for each announcement...")
    enrich_rns_bodies(delay=2.0)

    print(f"\n[4/4] Fetching price history from Yahoo Finance...")
    fetch_and_save_prices()

    print("\n" + "=" * 60)
    print("  Collection complete. Next step:")
    print("  python scripts/run_backtest.py")
    print("=" * 60)
