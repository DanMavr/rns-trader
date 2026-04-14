"""
Backtest simulator — reaction-based approach.

Signal logic:
  - Reaction detected using volume spike + price move on daily bar (bar X)
  - Entry: NEXT trading day open (realistic — signal seen after close of bar X)
  - Exits: T+1d close, T+5d close, T+20d close

This avoids same-bar bias (measuring the move that triggered the signal).
"""
from datetime import datetime, timedelta
from config.settings import TICKER, XAI_API_KEY
from src.collect.database import get_connection
from src.react.category_filter  import should_skip, get_priority
from src.react.context_filter   import get_price_context
from src.react.reaction_detector import detect_reaction, classify_timing


# ── Price helpers ─────────────────────────────────────────────────────────

def get_next_bar(ticker, from_date_str):
    """
    Returns the 1d bar for the NEXT trading day after from_date_str.
    Entry point: we see the reaction close-of-day, enter next day open.
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
    If fewer than N bars exist, returns the last available bar.
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
    if not rows:
        return None
    return dict(rows[-1])


def calc_return(entry, exit_price, direction="BUY"):
    if not entry or not exit_price or entry == 0:
        return None
    sign = 1 if direction == "BUY" else -1
    return round((exit_price - entry) / entry * 100 * sign, 4)


# ── Main backtest loop ────────────────────────────────────────────────────

def run_backtest(ticker=TICKER, use_llm=False):
    conn = get_connection()
    try:
        events = conn.execute("""
            SELECT * FROM rns_events
            WHERE ticker=? AND fetch_status='ok'
            ORDER BY datetime ASC
        """, (ticker,)).fetchall()
    finally:
        conn.close()
    events = [dict(e) for e in events]

    total = len(events)
    skipped = no_react = traded = 0

    print(f"\n  {total} events — {ticker}")
    print(f"  LLM: {'Grok (parallel)' if use_llm else 'Off'}")
    print(f"  {'─'*60}\n")

    for i, event in enumerate(events, 1):
        rns_id   = event["id"]
        dt_str   = event["datetime"]
        category = event["category"] or ""
        title    = event["title"]    or ""
        timing   = classify_timing(dt_str)

        print(f"[{i}/{total}] {dt_str[:16]}  {category:<5}  {title[:50]}")

        # Step 1 — Category filter
        if should_skip(category):
            print(f"  SKIP: {category} (routine admin)\n")
            _save_result(rns_id, ticker, timing, category,
                         skipped_category=1)
            skipped += 1
            continue

        priority = get_priority(category)
        print(f"  Priority: {priority}  Timing: {timing}")

        # Step 2 — Context filter
        ctx = get_price_context(ticker, dt_str[:10])
        print(f"  Setup: {ctx.get('setup_quality')}  "
              f"Position: {ctx.get('price_position','?')}  "
              f"Pre-vol: {ctx.get('pre_vol_ratio','?')}x")

        if ctx.get("skip"):
            print(f"  SKIP: context\n")
            _save_result(rns_id, ticker, timing, category,
                         ctx=ctx, skipped_context=1)
            skipped += 1
            continue

        # Step 3 — Reaction detector (daily bar)
        react = detect_reaction(ticker, dt_str)
        print(f"  Vol: {react['immediate_vol']:.0f} vs "
              f"{react['avg_vol_20d']:.0f} avg "
              f"({react['strength']:.1f}x)  "
              f"Price: {react['price_change_pct']:+.2f}%  "
              f"Bars: {react['bars_found']}")

        if not react["triggered"]:
            print(f"  No reaction\n")
            _save_result(rns_id, ticker, timing, category,
                         ctx=ctx, react=react)
            no_react += 1
            continue

        # Reaction confirmed
        direction     = "BUY" if react["direction"] == 1 else "SELL"
        reaction_date = react["reaction_date"]

        # Realistic entry: next trading day open
        # (signal observed after close of reaction day)
        next_bar    = get_next_bar(ticker, reaction_date)
        entry_price = next_bar["open"]          if next_bar else react["entry_price"]
        entry_date  = next_bar["datetime"][:10] if next_bar else reaction_date

        print(f"  TRIGGERED {react['strength']:.1f}x | "
              f"{react['price_change_pct']:+.2f}% | "
              f"Conf: {react['confidence']:.2f} -> {direction}")
        print(f"  Reaction day: {reaction_date}  "
              f"Entry: {entry_date} @ {entry_price:.2f}p")

        # Exit prices: T+1d, T+5d, T+20d (closes)
        bar_t1  = get_bar_n_days_after(ticker, reaction_date, 1)
        bar_t5  = get_bar_n_days_after(ticker, reaction_date, 5)
        bar_t20 = get_bar_n_days_after(ticker, reaction_date, 20)

        price_t1d  = bar_t1["close"]  if bar_t1  else None
        price_t5d  = bar_t5["close"]  if bar_t5  else None
        price_t20d = bar_t20["close"] if bar_t20 else None

        return_t1d  = calc_return(entry_price, price_t1d,  direction)
        return_t5d  = calc_return(entry_price, price_t5d,  direction)
        return_t20d = calc_return(entry_price, price_t20d, direction)

        outcome_t1d  = ("WIN" if (return_t1d  or 0) > 0 else "LOSS") \
                       if return_t1d  is not None else None
        outcome_t5d  = ("WIN" if (return_t5d  or 0) > 0 else "LOSS") \
                       if return_t5d  is not None else None
        outcome_t20d = ("WIN" if (return_t20d or 0) > 0 else "LOSS") \
                       if return_t20d is not None else None

        t1_str  = f"{return_t1d:+.2f}%"  if return_t1d  is not None else "-"
        t5_str  = f"{return_t5d:+.2f}%"  if return_t5d  is not None else "-"
        t20_str = f"{return_t20d:+.2f}%" if return_t20d is not None else "-"
        print(f"  T+1d={t1_str}  T+5d={t5_str}  T+20d={t20_str}")
        print(f"  {outcome_t1d or '?'} (T1)  "
              f"{outcome_t5d or '?'} (T5)  "
              f"{outcome_t20d or '?'} (T20)\n")

        # Optional LLM scoring
        llm_score = llm_conf = llm_reason = model_used = None
        if use_llm and XAI_API_KEY:
            try:
                from src.score.scorer import score_rns
                from config.settings  import XAI_MODEL
                scored = score_rns(
                    ticker=ticker,
                    category=category,
                    headlinename=event.get("headlinename", ""),
                    title=title,
                    body_text=event.get("body_text", ""),
                )
                if scored:
                    llm_score  = scored.get("score")
                    llm_conf   = scored.get("confidence")
                    llm_reason = scored.get("reason")
                    model_used = XAI_MODEL
                    print(f"  [Grok] {llm_score:+d} {llm_conf} - {llm_reason[:50]}")
            except Exception as e:
                print(f"  [Grok] error: {e}")

        traded += 1
        _save_result(
            rns_id, ticker, timing, category,
            ctx=ctx, react=react,
            would_trade=1, direction=direction,
            entry_price=entry_price, entry_time=entry_date,
            price_t1d=price_t1d, price_t5d=price_t5d, price_t20d=price_t20d,
            return_t1d=return_t1d, return_t5d=return_t5d, return_t20d=return_t20d,
            outcome_t1d=outcome_t1d, outcome_t5d=outcome_t5d, outcome_t20d=outcome_t20d,
            llm_score=llm_score, llm_confidence=llm_conf,
            llm_reason=llm_reason, model_used=model_used,
        )

    print(f"\n  {'='*60}")
    print(f"  {ticker} backtest complete")
    print(f"  Total: {total}  |  Skipped: {skipped}  |  "
          f"No reaction: {no_react}  |  Traded: {traded}")
    print(f"  {'='*60}")
    return traded


# ── Save result ───────────────────────────────────────────────────────────

def _save_result(rns_id, ticker, timing, category,
                 ctx=None, react=None,
                 skipped_category=0, skipped_context=0,
                 would_trade=0, direction=None,
                 entry_price=None, entry_time=None,
                 price_t1d=None, price_t5d=None, price_t20d=None,
                 return_t1d=None, return_t5d=None, return_t20d=None,
                 outcome_t1d=None, outcome_t5d=None, outcome_t20d=None,
                 llm_score=None, llm_confidence=None,
                 llm_reason=None, model_used=None):
    ctx   = ctx   or {}
    react = react or {}
    conn = get_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO backtest_results (
                rns_id, ticker, timing, category, category_priority,
                skipped_category, price_position, above_sma20,
                ret5d, ret60d, pre_vol_ratio, setup_quality, skipped_context,
                reaction_triggered, reaction_strength, reaction_direction,
                reaction_confidence, reaction_price_chg,
                avg_vol_20d, immediate_vol, bars_found, reaction_date,
                would_trade, direction, entry_price, entry_time,
                price_t1d, price_t5d, price_t20d,
                return_t1d, return_t5d, return_t20d,
                outcome_t1d, outcome_t5d, outcome_t20d,
                model_used, llm_score, llm_confidence, llm_reason
            ) VALUES (
                :rns_id, :ticker, :timing, :category, :category_priority,
                :skipped_category, :price_position, :above_sma20,
                :ret5d, :ret60d, :pre_vol_ratio, :setup_quality, :skipped_context,
                :reaction_triggered, :reaction_strength, :reaction_direction,
                :reaction_confidence, :reaction_price_chg,
                :avg_vol_20d, :immediate_vol, :bars_found, :reaction_date,
                :would_trade, :direction, :entry_price, :entry_time,
                :price_t1d, :price_t5d, :price_t20d,
                :return_t1d, :return_t5d, :return_t20d,
                :outcome_t1d, :outcome_t5d, :outcome_t20d,
                :model_used, :llm_score, :llm_confidence, :llm_reason
            )
        """, dict(
            rns_id=rns_id, ticker=ticker, timing=timing,
            category=category, category_priority=get_priority(category),
            skipped_category=skipped_category,
            price_position=ctx.get("price_position"),
            above_sma20=1 if ctx.get("above_sma20") else 0,
            ret5d=ctx.get("ret5d"), ret60d=ctx.get("ret60d"),
            pre_vol_ratio=ctx.get("pre_vol_ratio"),
            setup_quality=ctx.get("setup_quality"),
            skipped_context=skipped_context,
            reaction_triggered=1 if react.get("triggered") else 0,
            reaction_strength=react.get("strength"),
            reaction_direction=react.get("direction"),
            reaction_confidence=react.get("confidence"),
            reaction_price_chg=react.get("price_change_pct"),
            avg_vol_20d=react.get("avg_vol_20d"),
            immediate_vol=react.get("immediate_vol"),
            bars_found=react.get("bars_found"),
            reaction_date=react.get("reaction_date"),
            would_trade=would_trade, direction=direction,
            entry_price=entry_price, entry_time=entry_time,
            price_t1d=price_t1d, price_t5d=price_t5d, price_t20d=price_t20d,
            return_t1d=return_t1d, return_t5d=return_t5d, return_t20d=return_t20d,
            outcome_t1d=outcome_t1d, outcome_t5d=outcome_t5d, outcome_t20d=outcome_t20d,
            model_used=model_used, llm_score=llm_score,
            llm_confidence=llm_confidence, llm_reason=llm_reason,
        ))
        conn.commit()
    finally:
        conn.close()
