"""
Reaction detector — daily bar signal.
Detects significant market reaction to an RNS using daily price/volume.
- Volume : day-of-RNS total volume vs 20-day average daily volume
- Price  : (close - open) / open on the reaction day
- Timing : pre_market/intraday → same day; post_market → next trading day
No text. No LLM. Pure market-validated signal.
"""
from datetime import datetime, timedelta
from src.collect.database import get_connection


def get_20d_avg_volume(ticker: str, rns_date: str) -> float:
    """
    Average daily volume over the 20 trading days before rns_date.
    Uses 1d bars only.
    Returns 0.0 if fewer than 5 days of history available.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT volume FROM price_bars
        WHERE ticker = ?
          AND interval = '1d'
          AND SUBSTR(datetime, 1, 10) < ?
        ORDER BY datetime DESC
        LIMIT 20
    """, (ticker, rns_date)).fetchall()
    conn.close()
    if not rows or len(rows) < 5:
        return 0.0
    return float(sum(r[0] for r in rows) / len(rows))


def classify_timing(dt_str: str) -> str:
    """Classify RNS as pre_market / intraday / post_market / unknown."""
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


def get_reaction_date(rns_dt_str: str, timing: str) -> str:
    """
    Return the date (YYYY-MM-DD) on which the market reaction is expected.
    pre_market / intraday -> same calendar date as RNS.
    post_market           -> next calendar date (market opens next day).
    """
    if timing == "post_market":
        try:
            dt = datetime.fromisoformat(rns_dt_str.replace("Z", ""))
            return (dt + timedelta(days=1)).strftime("%Y-%m-%d")
        except Exception:
            pass
    return rns_dt_str[:10]


def detect_reaction(
    ticker:         str,
    rns_dt_str:     str,
    vol_multiplier: float = 3.0,
    price_move_pct: float = 3.5,
) -> dict:
    """
    Daily bar reaction detector.

    Looks up the 1d bar for the reaction date and compares:
      - immediate_vol : full day volume on reaction date
      - avg_vol_20d   : average daily volume over prior 20 trading days
      - price_change_pct : (close - open) / open * 100 on reaction date

    Triggers when BOTH:
      - immediate_vol > avg_vol_20d * vol_multiplier  (default 3x)
      - abs(price_change_pct) > price_move_pct        (default 3.5%)

    Returns dict with:
      triggered, strength, direction, confidence,
      price_change_pct, entry_price, avg_vol_20d, immediate_vol,
      timing, reaction_date, bars_found.
    """
    timing        = classify_timing(rns_dt_str)
    reaction_date = get_reaction_date(rns_dt_str, timing)

    result = {
        "triggered":         False,
        "strength":          0.0,
        "direction":         0,
        "confidence":        0.0,
        "price_change_pct":  0.0,
        "entry_price":       None,
        "avg_vol_20d":       0.0,
        "immediate_vol":     0.0,
        "timing":            timing,
        "reaction_date":     reaction_date,
        "bars_found":        0,
    }

    if timing == "unknown":
        return result

    # Fetch the daily bar for the reaction date
    conn = get_connection()
    bar = conn.execute("""
        SELECT datetime, open, high, low, close, volume
        FROM price_bars
        WHERE ticker   = ?
          AND interval = '1d'
          AND SUBSTR(datetime, 1, 10) = ?
        LIMIT 1
    """, (ticker, reaction_date)).fetchone()
    conn.close()

    if not bar:
        # Weekend / bank holiday — no bar exists, signal cannot fire
        return result

    result["bars_found"] = 1
    bar = dict(bar)

    avg_vol_20d      = get_20d_avg_volume(ticker, reaction_date)
    immediate_vol    = bar["volume"]
    entry_price      = bar["open"]
    price_change_pct = (bar["close"] - entry_price) / entry_price * 100 \
                       if entry_price else 0.0

    result["avg_vol_20d"]      = round(avg_vol_20d, 0)
    result["immediate_vol"]    = round(float(immediate_vol), 0)
    result["price_change_pct"] = round(price_change_pct, 3)
    result["entry_price"]      = entry_price

    if avg_vol_20d == 0:
        return result

    vol_ok   = immediate_vol > avg_vol_20d * vol_multiplier
    price_ok = abs(price_change_pct) > price_move_pct

    if not (vol_ok and price_ok):
        return result

    strength  = immediate_vol / avg_vol_20d
    direction = 1 if price_change_pct > 0 else -1

    result.update({
        "triggered":  True,
        "strength":   round(strength, 2),
        "direction":  direction,
        "confidence": round(min(1.0, strength / 6.0), 3),
    })
    return result
