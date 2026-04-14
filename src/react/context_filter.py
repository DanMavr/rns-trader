"""
Context filter — checks price position and pre-RNS volume trend
to classify the trading setup at the time of each announcement.

Queries daily (1d) price bars only.
All datetime comparisons use SUBSTR(datetime,1,10) for robustness
against both space-format ('2024-06-15 00:00:00') and
T-format ('2024-06-15T00:00:00') stored dates.
"""
from src.collect.database import get_connection


def get_price_context(ticker: str, rns_date: str) -> dict:
    """
    Returns price context for a ticker on a given RNS date.

    Inputs:
      ticker   : e.g. 'MATD'
      rns_date : YYYY-MM-DD string

    Checks:
      price_position : where price sits in its 52-week range (0=low, 1=high)
      above_sma20    : is price above its 20-day simple moving average
      ret5d          : 5-day return leading into the announcement
      ret60d         : 60-day return — if >150% skip (momentum exhaustion)
      pre_vol_ratio  : 5d avg volume / 20d avg volume (accumulation signal)

    Setup quality:
      strong   — price in lower 35% of 52-week range (buying opportunity)
      neutral  — price in middle 30% of range
      extended — price in upper 35% of range (momentum risk)
      skip     — ret60d > 150% (exhausted move, avoid)

    Note: 'extended' is NOT a hard skip. It is recorded and passed to the
    reaction detector. The backtest will reveal whether extended setups
    produce worse outcomes — we do not pre-emptively exclude them.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT SUBSTR(datetime, 1, 10) as date, close, volume
        FROM price_bars
        WHERE ticker   = ?
          AND interval = '1d'
          AND SUBSTR(datetime, 1, 10) < ?
        ORDER BY datetime DESC
        LIMIT 252
    """, (ticker, rns_date)).fetchall()
    conn.close()

    if not rows or len(rows) < 5:
        return {"setup_quality": "neutral", "skip": False}

    rows    = [dict(r) for r in rows]
    closes  = [r["close"]  for r in rows]
    volumes = [r["volume"] for r in rows]

    current_price = closes[0]

    year_high      = max(closes[:252])
    year_low       = min(closes[:252])
    price_range    = year_high - year_low
    price_position = (current_price - year_low) / price_range \
                     if price_range > 0 else 0.5

    sma20       = sum(closes[:20]) / min(20, len(closes))
    above_sma20 = current_price > sma20

    ret5d = round((closes[0] - closes[5]) / closes[5] * 100, 2) \
            if len(closes) >= 6 else None

    avg_vol_20d   = sum(volumes[:20]) / min(20, len(volumes))
    avg_vol_5d    = sum(volumes[:5])  / min(5,  len(volumes))
    pre_vol_ratio = avg_vol_5d / avg_vol_20d if avg_vol_20d > 0 else 1.0

    ret60d = round((closes[0] - closes[59]) / closes[59] * 100, 2) \
             if len(closes) >= 60 else None

    # Hard skip: momentum exhaustion — stock already ran >150% in 60 days
    skip = bool(ret60d and ret60d > 150)

    if skip:
        setup_quality = "skip"
    elif price_position < 0.35:
        setup_quality = "strong"
    elif price_position < 0.65:
        setup_quality = "neutral"
    else:
        setup_quality = "extended"

    return {
        "current_price":  current_price,
        "price_position": round(price_position, 3),
        "year_high":      year_high,
        "year_low":       year_low,
        "above_sma20":    above_sma20,
        "ret5d":          ret5d,
        "ret60d":         ret60d,
        "pre_vol_ratio":  round(pre_vol_ratio, 2),
        "setup_quality":  setup_quality,
        "skip":           skip,
    }
