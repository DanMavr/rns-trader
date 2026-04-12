import sqlite3
from datetime import datetime, timedelta
import pytz
from config.settings import (
    DB_PATH, TICKER, TRADE_SCORE_THRESHOLD,
    TRADE_CONFIDENCE_NEEDED, XAI_MODEL,
)
from src.score.scorer import score_rns
from src.collect.database import get_connection

MARKET_OPEN_HOUR  = 8
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MIN  = 30
UK_TZ = pytz.timezone("Europe/London")


def classify_timing(dt_str):
    """
    Classify an RNS announcement as pre_market, intraday, or post_market.
    dt_str example: '2025-09-29T06:05:00' or '2025-09-29T07:00:00'
    """
    try:
        dt = datetime.fromisoformat(dt_str)
        total_mins = dt.hour * 60 + dt.minute
        open_mins  = MARKET_OPEN_HOUR * 60
        close_mins = MARKET_CLOSE_HOUR * 60 + MARKET_CLOSE_MIN

        if total_mins < open_mins:
            return "pre_market"
        elif total_mins > close_mins:
            return "post_market"
        else:
            return "intraday"
    except Exception:
        return "unknown"


def get_price_at(ticker, dt_str, interval="5m"):
    """Get the nearest 5-min bar at or after dt_str."""
    conn = get_connection()
    row = conn.execute("""
        SELECT * FROM price_bars
        WHERE ticker=? AND interval=?
          AND datetime >= ?
        ORDER BY datetime ASC
        LIMIT 1
    """, (ticker, interval, dt_str)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_price_n_minutes_after(ticker, dt_str, minutes):
    """Get price approximately N minutes after dt_str."""
    try:
        dt     = datetime.fromisoformat(dt_str)
        target = dt + timedelta(minutes=minutes)
        return get_price_at(ticker, target.isoformat())
    except Exception:
        return None


def get_eod_price(ticker, date_str):
    """Get end-of-day close from daily bars."""
    conn = get_connection()
    row = conn.execute("""
        SELECT * FROM price_bars
        WHERE ticker=? AND interval='1d'
          AND datetime >= ?
        ORDER BY datetime ASC
        LIMIT 1
    """, (ticker, date_str)).fetchone()
    conn.close()
    return dict(row) if row else None


def calc_return(entry, exit_price, direction="BUY"):
    """Calculate percentage return."""
    if not entry or not exit_price or entry == 0:
        return None
    sign = 1 if direction == "BUY" else -1
    return round((exit_price - entry) / entry * 100 * sign, 4)


def already_scored(rns_id, model_used):
    """Check if this event has already been scored by this model."""
    conn = get_connection()
    row = conn.execute("""
        SELECT id FROM backtest_results
        WHERE rns_id=? AND model_used=?
    """, (rns_id, model_used)).fetchone()
    conn.close()
    return row is not None


def run_backtest(ticker=TICKER):
    conn = get_connection()

    events = conn.execute("""
        SELECT * FROM rns_events
        WHERE ticker=? AND fetch_status='ok'
        ORDER BY datetime ASC
    """, (ticker,)).fetchall()
    conn.close()

    events = [dict(e) for e in events]
    total  = len(events)
    print(f"\n  {total} announcements to score...\n")

    scored = 0
    skipped = 0
    traded = 0

    for i, event in enumerate(events, 1):
        rns_id   = event["id"]
        dt_str   = event["datetime"]
        title    = event["title"]
        category = event["category"]
        timing   = classify_timing(dt_str)

        print(f"[{i}/{total}] {dt_str[:16]}  {category:<5}  {title[:55]}")
        print(f"  Timing: {timing}")

        # Skip if already scored by this model
        if already_scored(rns_id, XAI_MODEL):
            print(f"  Already scored by {XAI_MODEL} — skipping")
            skipped += 1
            continue

        # Score with Grok
        result = score_rns(
            ticker        = ticker,
            company_name  = "Petro Matad Limited",
            category      = event["category"],
            headlinename  = event["headlinename"],
            title         = title,
            body_text     = event["body_text"] or "",
        )

        if not result:
            print(f"  SKIP: scoring failed")
            skipped += 1
            continue

        llm_score      = result.get("score", 0)
        llm_confidence = result.get("confidence", "low")
        llm_reason     = result.get("reason", "")

        print(f"  Score={llm_score:+d}  Conf={llm_confidence}  {llm_reason}")

        # Determine entry time based on timing
        if timing == "intraday":
            entry_time = dt_str
        else:
            # Pre/post market — entry at next market open
            entry_time = dt_str[:10] + "T08:01:00"

        # Get entry price (5-min bar)
        entry_bar = get_price_at(ticker, entry_time)
        if not entry_bar:
            print(f"  No intraday price data — trying daily bar")
            eod = get_eod_price(ticker, dt_str[:10])
            entry_price = eod["open"] if eod else None
        else:
            entry_price = entry_bar["open"]

        if not entry_price:
            print(f"  SKIP: no price data for {entry_time}")
            skipped += 1
            continue

        # Determine trade direction
        would_trade = (
            abs(llm_score) >= TRADE_SCORE_THRESHOLD and
            llm_confidence == TRADE_CONFIDENCE_NEEDED
        )
        direction = None
        if would_trade:
            direction = "BUY" if llm_score > 0 else "SELL"
            traded += 1

        # Get exit prices at T+5, T+15, T+30, T+60
        prices = {}
        for mins in [5, 15, 30, 60]:
            bar = get_price_n_minutes_after(ticker, entry_time, mins)
            prices[f"t{mins}"] = bar["close"] if bar else None

        # EOD price
        eod_bar   = get_eod_price(ticker, dt_str[:10])
        price_eod = eod_bar["close"] if eod_bar else None

        # Calculate returns
        returns = {}
        for mins in [5, 15, 30, 60]:
            returns[f"t{mins}"] = calc_return(
                entry_price, prices[f"t{mins}"], direction or "BUY"
            )
        return_eod = calc_return(entry_price, price_eod, direction or "BUY")

        # Outcomes
        outcome_t15 = None
        outcome_eod = None
        if would_trade and returns["t15"] is not None:
            outcome_t15 = "WIN" if returns["t15"] > 0 else "LOSS"
        if would_trade and return_eod is not None:
            outcome_eod = "WIN" if return_eod > 0 else "LOSS"

        t15_str = f"{returns['t15']:+.2f}%" if returns["t15"] else "—"
        eod_str = f"{return_eod:+.2f}%" if return_eod else "—"
        print(f"  Entry={entry_price:.2f}p  T+15={t15_str}  EOD={eod_str}"
              f"  Trade: {'YES → ' + direction + ' → ' + (outcome_t15 or '?') if would_trade else 'no'}")

        # Save to DB
        conn = get_connection()
        conn.execute("""
            INSERT INTO backtest_results (
                rns_id, ticker, model_used, timing,
                llm_score, llm_confidence, llm_reason,
                would_trade, direction,
                entry_price, entry_time,
                price_t5, price_t15, price_t30, price_t60, price_eod,
                return_t5, return_t15, return_t30, return_t60, return_eod,
                outcome_t15, outcome_eod
            ) VALUES (
                :rns_id, :ticker, :model_used, :timing,
                :llm_score, :llm_confidence, :llm_reason,
                :would_trade, :direction,
                :entry_price, :entry_time,
                :price_t5, :price_t15, :price_t30, :price_t60, :price_eod,
                :return_t5, :return_t15, :return_t30, :return_t60, :return_eod,
                :outcome_t15, :outcome_eod
            )
        """, dict(
            rns_id         = rns_id,
            ticker         = ticker,
            model_used     = XAI_MODEL,
            timing         = timing,
            llm_score      = llm_score,
            llm_confidence = llm_confidence,
            llm_reason     = llm_reason,
            would_trade    = 1 if would_trade else 0,
            direction      = direction,
            entry_price    = entry_price,
            entry_time     = entry_time,
            price_t5       = prices["t5"],
            price_t15      = prices["t15"],
            price_t30      = prices["t30"],
            price_t60      = prices["t60"],
            price_eod      = price_eod,
            return_t5      = returns["t5"],
            return_t15     = returns["t15"],
            return_t30     = returns["t30"],
            return_t60     = returns["t60"],
            return_eod     = return_eod,
            outcome_t15    = outcome_t15,
            outcome_eod    = outcome_eod,
        ))
        conn.commit()
        conn.close()
        scored += 1
        print()

    print(f"\n{'='*60}")
    print(f"  Backtest complete")
    print(f"  Scored:  {scored}")
    print(f"  Skipped: {skipped}")
    print(f"  Would-trade signals: {traded}")
    print(f"  Model: {XAI_MODEL}")
    print(f"{'='*60}")
