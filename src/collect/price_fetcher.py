import yfinance as yf
from src.collect.database import get_connection
from config.settings import TICKER, TICKER_YF


def fetch_and_store_prices(ticker=TICKER, yf_symbol=TICKER_YF,
                           interval="1d", period="2y"):
    """
    Fetch price bars from Yahoo Finance and store in price_bars table.

    For 1d bars: datetime stored as YYYY-MM-DD (date only).
    For intraday bars: datetime stored as YYYY-MM-DDTHH:MM:SS.

    This ensures the UNIQUE(ticker, interval, datetime) constraint
    correctly prevents duplicates regardless of yfinance timezone offsets.
    """
    print(f"  Fetching {interval} bars for {ticker} ({yf_symbol}) period={period}...")
    try:
        df = yf.download(
            yf_symbol,
            period=period,
            interval=interval,
            auto_adjust=True,
            progress=False
        )
    except Exception as e:
        print(f"  Yahoo Finance error for {ticker}: {e}")
        return 0

    if df.empty:
        print(f"  No data returned for {ticker}")
        return 0

    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)

    conn = get_connection()
    inserted = 0

    for ts, row in df.iterrows():
        # Normalise datetime format:
        # 1d bars  → "YYYY-MM-DD"          (no time — avoids timezone dup bug)
        # intraday → "YYYY-MM-DDTHH:MM:SS" (keep time for intraday precision)
        if interval == "1d":
            dt_str = str(ts)[:10]  # always "YYYY-MM-DD"
        else:
            try:
                dt_str = ts.strftime("%Y-%m-%dT%H:%M:%S")
            except Exception:
                dt_str = str(ts)[:19]

        try:
            conn.execute("""
                INSERT OR IGNORE INTO price_bars
                    (ticker, interval, datetime, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker, interval, dt_str,
                float(row.get("Open",  0) or 0),
                float(row.get("High",  0) or 0),
                float(row.get("Low",   0) or 0),
                float(row.get("Close", 0) or 0),
                int(row.get("Volume",  0) or 0),
            ))
            if conn.total_changes:
                inserted += 1
        except Exception as e:
            print(f"  Insert error {ts}: {e}")

    conn.commit()
    conn.close()
    print(f"  {inserted} new {interval} bars stored for {ticker}")
    return inserted
