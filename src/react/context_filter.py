"""
Context filter — checks price position and pre-RNS volume
to weight signals and avoid bad setups.
Two SQL queries against existing price_bars data.
"""
from src.collect.database import get_connection


def get_price_context(ticker: str, rns_date: str) -> dict:
    """
    Returns price context for a ticker on a given date.
    Checks price vs 52-week range, 20-day SMA, 5-day momentum,
    and pre-RNS volume accumulation.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT datetime, close, volume
        FROM price_bars
        WHERE ticker = ?
          AND interval = '1d'
          AND datetime <= ?
        ORDER BY datetime DESC
        LIMIT 252
    """, (ticker, rns_date + "T23:59:59")).fetchall()
    conn.close()

    if not rows or len(rows) < 5:
        return {"setup_quality": "neutral", "skip": False}

    closes  = [r["close"]  for r in rows]
    volumes = [r["volume"] for r in rows]

    current_price = closes[0]

    year_high = max(closes[:252])
    year_low  = min(closes[:252])
    price_range = year_high - year_low
    price_position = (current_price - year_low) / price_range \
                     if price_range > 0 else 0.5

    sma20       = sum(closes[:20]) / min(20, len(closes))
    above_sma20 = current_price > sma20

    ret5d = round((closes[0] - closes[5]) / closes[5] * 100, 2) \
            if len(closes) >= 6 else None

    avg_vol_20d   = sum(volumes[:20]) / min(20, len(volumes))
    avg_vol_5d    = sum(volumes[:5])  / min(5,  len(volumes))
    pre_vol_ratio = avg_vol_5d / avg_vol_20d if avg_vol_20d > 0 else 1.0

    ret60d = (closes[0] - closes[59]) / closes[59] * 100 \
             if len(closes) >= 60 else None

    # Skip if already had massive run — momentum exhaustion risk
    skip = bool(ret60d and ret60d > 150)

    if price_position < 0.35 and not skip:
        setup_quality = "strong"
    elif price_position < 0.65 and not skip:
        setup_quality = "neutral"
    elif skip:
        setup_quality = "skip"
    else:
        setup_quality = "extended"

    return {
        "current_price":  current_price,
        "price_position": round(price_position, 3),
        "year_high":      year_high,
        "year_low":       year_low,
        "above_sma20":    above_sma20,
        "ret5d":          ret5d,
        "ret60d":         round(ret60d, 2) if ret60d else None,
        "pre_vol_ratio":  round(pre_vol_ratio, 2),
        "setup_quality":  setup_quality,
        "skip":           skip,
    }
