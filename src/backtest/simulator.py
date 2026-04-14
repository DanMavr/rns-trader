def get_next_bar(ticker, from_date_str):
    """
    Returns the 1d bar for the NEXT trading day after from_date_str.
    Used for realistic entry: we see the reaction close-of-day, 
    then enter at next day's open.
    """
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT * FROM price_bars
            WHERE ticker=? AND interval='1d'
              AND SUBSTR(datetime,1,10) > ?
            ORDER BY datetime ASC LIMIT 1
        """, (ticker, from_date_str)).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def get_bar_n_days_after(ticker, from_date_str, n):
    """
    Returns the 1d bar approximately N trading days after from_date_str.
    Fetches the Nth row forward from that date.
    """
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM price_bars
            WHERE ticker=? AND interval='1d'
              AND SUBSTR(datetime,1,10) > ?
            ORDER BY datetime ASC LIMIT ?
        """, (ticker, from_date_str, n)).fetchall()
    finally:
        conn.close()
    if rows and len(rows) >= n:
        return dict(rows[-1])
    elif rows:
        return dict(rows[-1])  # best available
    return None


def get_eod_price(ticker, date_str):
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT * FROM price_bars
            WHERE ticker=? AND interval='1d'
              AND SUBSTR(datetime,1,10) >= ?
            ORDER BY datetime ASC LIMIT 1
        """, (ticker, date_str)).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def calc_return(entry, exit_price, direction="BUY"):
    if not entry or not exit_price or entry == 0:
        return None
    sign = 1 if direction == "BUY" else -1
    return round((exit_price - entry) / entry * 100 * sign, 4)
