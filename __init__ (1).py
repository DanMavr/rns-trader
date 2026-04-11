import yfinance as yf
import pandas as pd
from config.settings import TICKER_YF, TICKER
from src.collect.database import get_connection


def fetch_and_save_prices(ticker_yf=TICKER_YF, ticker=TICKER):
    """Fetch price history from Yahoo Finance and store in DB."""
    conn = get_connection()

    # --- Daily bars: 2 years ---
    print(f"Fetching daily prices for {ticker_yf}...")
    try:
        daily = yf.Ticker(ticker_yf).history(period="2y", interval="1d")
        daily = daily.reset_index()
        count = 0
        for _, row in daily.iterrows():
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO price_bars
                        (ticker, datetime, interval, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (ticker,
                      str(row["Date"])[:10] + "T08:00:00",
                      "1d",
                      round(float(row["Open"]), 4),
                      round(float(row["High"]), 4),
                      round(float(row["Low"]), 4),
                      round(float(row["Close"]), 4),
                      int(row["Volume"])))
                count += 1
            except Exception:
                pass
        conn.commit()
        print(f"  Saved {count} daily bars")
    except Exception as e:
        print(f"  Daily fetch failed: {e}")

    # --- Intraday: last 60 days at 5-min resolution ---
    print(f"Fetching 5-min intraday prices for {ticker_yf}...")
    try:
        intra = yf.Ticker(ticker_yf).history(period="60d", interval="5m")
        intra = intra.reset_index()
        count = 0
        for _, row in intra.iterrows():
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO price_bars
                        (ticker, datetime, interval, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (ticker,
                      str(row["Datetime"])[:19],
                      "5m",
                      round(float(row["Open"]), 4),
                      round(float(row["High"]), 4),
                      round(float(row["Low"]), 4),
                      round(float(row["Close"]), 4),
                      int(row["Volume"])))
                count += 1
            except Exception:
                pass
        conn.commit()
        print(f"  Saved {count} intraday 5-min bars")
    except Exception as e:
        print(f"  Intraday fetch failed: {e}")

    conn.close()


def get_price_at(ticker, dt_str, interval="5m"):
    """
    Get the nearest price bar at or after dt_str.
    Falls back to daily bar if 5m not available.
    Returns dict or None.
    """
    conn = get_connection()
    row = conn.execute("""
        SELECT * FROM price_bars
        WHERE ticker=? AND interval=? AND datetime >= ?
        ORDER BY datetime ASC LIMIT 1
    """, (ticker, interval, dt_str)).fetchone()

    if not row:
        row = conn.execute("""
            SELECT * FROM price_bars
            WHERE ticker=? AND interval='1d' AND datetime >= ?
            ORDER BY datetime ASC LIMIT 1
        """, (ticker, dt_str[:10])).fetchone()

    conn.close()
    return dict(row) if row else None


def get_price_after_minutes(ticker, entry_dt_str, minutes, interval="5m"):
    """Get closing price N minutes after entry datetime string."""
    from datetime import datetime, timedelta
    try:
        entry_dt = datetime.fromisoformat(entry_dt_str.replace("Z", ""))
        target_dt = entry_dt + timedelta(minutes=minutes)
        target_str = target_dt.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return None

    conn = get_connection()
    row = conn.execute("""
        SELECT close FROM price_bars
        WHERE ticker=? AND interval=? AND datetime >= ?
        ORDER BY datetime ASC LIMIT 1
    """, (ticker, interval, target_str)).fetchone()

    if not row:
        row = conn.execute("""
            SELECT close FROM price_bars
            WHERE ticker=? AND interval='1d' AND datetime >= ?
            ORDER BY datetime ASC LIMIT 1
        """, (ticker, target_str[:10])).fetchone()

    conn.close()
    return float(row["close"]) if row else None


def get_eod_price(ticker, date_str):
    """Get end-of-day close price for a given date string YYYY-MM-DD."""
    conn = get_connection()
    row = conn.execute("""
        SELECT close FROM price_bars
        WHERE ticker=? AND interval='1d'
        AND datetime LIKE ?
        ORDER BY datetime DESC LIMIT 1
    """, (ticker, date_str[:10] + "%")).fetchone()
    conn.close()
    return float(row["close"]) if row else None
