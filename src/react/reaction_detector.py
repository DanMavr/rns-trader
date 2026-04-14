"""
Reaction detector — the core signal.
Watches first 15 min of price/volume after an RNS.
No text. No LLM. Pure market-validated signal.
"""
from datetime import datetime, timedelta
from src.collect.database import get_connection


def get_20d_avg_volume(ticker: str, rns_date: str) -> float:
    """
    Average volume of the first 3 x 5-min bars at open (08:00-08:15)
    across the 20 trading days before rns_date.
    This makes it directly comparable to immediate_vol.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT AVG(volume) FROM (
            SELECT SUM(volume) as volume
            FROM price_bars
            WHERE ticker = ?
              AND interval = '5m'
              AND datetime < ?
              AND SUBSTR(datetime, 12, 5) BETWEEN '08:00' AND '08:14'
            GROUP BY SUBSTR(datetime, 1, 10)
            ORDER BY SUBSTR(datetime, 1, 10) DESC
            LIMIT 20
        )
    """, (ticker, rns_date + ' 00:00:00')).fetchone()
    conn.close()
    return float(rows[0]) if rows and rows[0] else 0.0


def classify_timing(dt_str: str) -> str:
    """Classify RNS as pre_market / intraday / post_market."""
    try:
        dt   = datetime.fromisoformat(dt_str.replace("Z", ""))
        mins = dt.hour * 60 + dt.minute
        if mins < 8 * 60:
            return "pre_market"
        elif mins > 16 * 60 + 30:
            return "post_market"
        else:
            return "intraday"
    except Exception:
        return "unknown"


def get_reaction_start(rns_dt_str: str, timing: str) -> str:
    """Return datetime string at which to start watching for reaction."""
    if timing == "intraday":
        return rns_dt_str
    if timing == "pre_market":
        return rns_dt_str[:10] + "T08:00:00"
    if timing == "post_market":
        try:
            dt = datetime.fromisoformat(rns_dt_str.replace("Z", ""))
            return (dt + timedelta(days=1)).strftime("%Y-%m-%d") + "T08:00:00"
        except Exception:
            return rns_dt_str[:10] + "T08:00:00"
    return rns_dt_str


def detect_reaction(
    ticker:         str,
    rns_dt_str:     str,
    vol_multiplier: float = 4.0,
    price_move_pct: float = 3.5,
    n_bars:         int   = 3,
) -> dict:
    """
    Core reaction detector.
    Returns dict with: triggered, strength, direction, confidence,
    price_change_pct, entry_price, avg_vol_20d, immediate_vol,
    timing, start_time, bars_found.
    """
    timing     = classify_timing(rns_dt_str)
    start_time = get_reaction_start(rns_dt_str, timing)

    result = {
        "triggered": False, "strength": 0.0, "direction": 0,
        "confidence": 0.0, "price_change_pct": 0.0,
        "entry_price": None, "avg_vol_20d": 0.0,
        "immediate_vol": 0.0, "timing": timing,
        "start_time": start_time, "bars_found": 0,
    }

    if timing == "unknown":
        return result

    conn = get_connection()
    bars = conn.execute("""
        SELECT datetime, open, high, low, close, volume
        FROM price_bars
        WHERE ticker = ? AND interval = '5m' AND datetime >= ?
        ORDER BY datetime ASC LIMIT ?
    """, (ticker, start_time.replace('T', ' '), n_bars)).fetchall()
    conn.close()

    result["bars_found"] = len(bars)
    if len(bars) < 2:
        return result

    watch = [dict(b) for b in bars]

    avg_vol_20d   = get_20d_avg_volume(ticker, rns_dt_str[:10])
    immediate_vol = sum(b["volume"] for b in watch) / len(watch)
    entry_price   = watch[0]["open"]
    final_close   = watch[-1]["close"]
    price_change_pct = (final_close - entry_price) / entry_price * 100 \
                       if entry_price else 0.0

    result["avg_vol_20d"]    = round(avg_vol_20d, 0)
    result["immediate_vol"]  = round(immediate_vol, 0)
    result["price_change_pct"] = round(price_change_pct, 3)
    result["entry_price"]    = entry_price

    vol_ok   = avg_vol_20d > 0 and immediate_vol > avg_vol_20d * vol_multiplier
    price_ok = abs(price_change_pct) > price_move_pct

    if not (vol_ok and price_ok):
        return result

    strength  = immediate_vol / avg_vol_20d if avg_vol_20d > 0 else 0.0
    direction = 1 if price_change_pct > 0 else -1

    result.update({
        "triggered":  True,
        "strength":   round(strength, 2),
        "direction":  direction,
        "confidence": round(min(1.0, strength / 8.0), 3),
    })
    return result
