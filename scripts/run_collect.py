"""
Multi-ticker RNS + price collector.

Usage:
  python scripts/run_collect.py              # all tickers
  python scripts/run_collect.py MATD         # single ticker
  python scripts/run_collect.py MATD PANR    # specific tickers
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.collect.database      import init_db
from src.collect.rns_fetcher   import fetch_rns_list, save_rns_list, enrich_rns_bodies
from src.collect.price_fetcher import fetch_and_store_prices
from config.settings import TICKERS, DEFAULT_TICKER


def collect_ticker(ticker: str, cfg: dict):
    print(f"\n{'─'*60}")
    print(f"  {ticker} — {cfg['name']}")
    print(f"{'─'*60}")

    print(f"  Fetching RNS list...")
    items = fetch_rns_list(ticker=ticker, issuer_name=cfg["slug"])
    print(f"  {len(items)} announcements found")
    save_rns_list(items, ticker=ticker)

    print(f"  Enriching RNS bodies...")
    enrich_rns_bodies(ticker=ticker)

    print(f"  Fetching daily price bars...")
    fetch_and_store_prices(ticker=ticker, yf_symbol=cfg["yf"], interval="1d", period="2y")

    print(f"  Fetching 5-min intraday bars...")
    fetch_and_store_prices(ticker=ticker, yf_symbol=cfg["yf"], interval="5m", period="60d")

    print(f"  Done: {ticker}")


if __name__ == "__main__":
    init_db()

    requested = sys.argv[1:]
    if requested:
        tickers_to_run = {t: TICKERS[t] for t in requested if t in TICKERS}
        missing = [t for t in requested if t not in TICKERS]
        if missing:
            print(f"Warning: unknown tickers {missing}")
    else:
        tickers_to_run = TICKERS

    print("=" * 60)
    print(f"  RNS TRADER — Multi-Ticker Collector")
    print(f"  Tickers: {list(tickers_to_run.keys())}")
    print("=" * 60)

    for ticker, cfg in tickers_to_run.items():
        try:
            collect_ticker(ticker, cfg)
        except Exception as e:
            print(f"  ERROR on {ticker}: {e}")
            continue

    print("\n" + "=" * 60)
    print(f"  Collection complete — {len(tickers_to_run)} tickers")
    print(f"  Next: python scripts/run_backtest.py")
    print("=" * 60)
