"""
Backtest simulator — reaction-based approach.
Primary signal:  volume spike + price move after RNS
Pre-filter:      category code
Context filter:  price position + pre-RNS volume
LLM (optional):  Grok score for comparison only
"""
from datetime import datetime, timedelta
from config.settings import TICKER, XAI_API_KEY
from src.collect.database import get_connection
from src.react.category_filter  import should_skip, get_priority
from src.react.context_filter   import get_price_context
from src.react.reaction_detector import (
    detect_reaction, classify_timing, get_reaction_date
)



def get_eod_price(ticker, date_str):
    conn = get_connection()
    row = conn.execute("""
        SELECT * FROM price_bars
        WHERE ticker=? AND interval='1d' AND datetime >= ?
        ORDER BY datetime ASC LIMIT 1
    """, (ticker, date_str)).fetchone()
    conn.close()
    return dict(row) if row else None


def calc_return(entry, exit_price, direction="BUY"):
    if not entry or not exit_price or entry == 0:
        return None
    sign = 1 if direction == "BUY" else -1
    return round((exit_price - entry) / entry * 100 * sign, 4)


def run_backtest(ticker=TICKER, use_llm=False):
    conn = get_connection()
    events = conn.execute("""
        SELECT * FROM rns_events
        WHERE ticker=? AND fetch_status='ok'
        ORDER BY datetime ASC
    """, (ticker,)).fetchall()
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

        # Step 1: Category filter
        if should_skip(category):
            print(f"  SKIP: {category} (routine admin)\n")
            _save_result(rns_id, ticker, timing, category,
                         skipped_category=1)
            skipped += 1
            continue

        priority = get_priority(category)
        print(f"  Priority: {priority}  Timing: {timing}")

        # Step 2: Context filter
        ctx = get_price_context(ticker, dt_str[:10])
        print(f"  Setup: {ctx.get('setup_quality')}  "
              f"Position: {ctx.get('price_position','?')}  "
              f"Pre-vol: {ctx.get('pre_vol_ratio','?')}×")

        if ctx.get("skip"):
            print(f"  SKIP: context\n")
            _save_result(rns_id, ticker, timing, category,
                         ctx=ctx, skipped_context=1)
            skipped += 1
            continue

        # Step 3: Reaction detector
        react = detect_reaction(ticker, dt_str)
        print(f"  Vol: {react['immediate_vol']:.0f} vs "
              f"{react['avg_vol_20d']:.0f} avg "
              f"({react['strength']:.1f}×)  "
              f"Price: {react['price_change_pct']:+.2f}%  "
              f"Bars: {react['bars_found']}")

        if not react["triggered"]:
            print(f"  No reaction\n")
            _save_result(rns_id, ticker, timing, category,
                         ctx=ctx, react=react)
            no_react += 1
            continue

        # Reaction confirmed — enter trade
        direction   = "BUY" if react["direction"] == 1 else "SELL"
        entry_price = react["entry_price"]
        entry_time  = react["reaction_date"]

        print(f"  ✅ TRIGGERED {react['strength']:.1f}× | "
              f"{react['price_change_pct']:+.2f}% | "
              f"Conf: {react['confidence']:.2f} → {direction}")

        # Exit price — EOD only (daily bars)
        prices     = {}
        eod_bar    = get_eod_price(ticker, entry_time)
        price_eod  = eod_bar["close"] if eod_bar else None
        returns    = {}
        return_eod = calc_return(entry_price, price_eod, direction)

        outcome_eod = ("WIN" if (return_eod or 0) > 0 else "LOSS") \
                      if return_eod is not None else None

        eod_str = f"{return_eod:+.2f}%" if return_eod is not None else "—"
        print(f"  Entry={entry_price:.4f}p  EOD={eod_str}  {outcome_eod or '?'}\n")

        # Optional LLM
        llm_score = llm_conf = llm_reason = model_used = None
        if use_llm and XAI_API_KEY:
            try:
                from src.score.scorer import score_rns
                from config.settings  import XAI_MODEL
                scored = score_rns(
                    ticker=ticker,
                    company_name="Petro Matad Limited",
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
                    print(f"  [Grok] {llm_score:+d} {llm_conf} — {llm_reason[:50]}")
            except Exception as e:
                print(f"  [Grok] error: {e}")

        traded += 1
        _save_result(
            rns_id, ticker, timing, category,
            ctx=ctx, react=react,
            would_trade=1, direction=direction,
            entry_price=entry_price, entry_time=entry_time,
            prices=prices, price_eod=price_eod,
            returns=returns, return_eod=return_eod,
            outcome_t15=None, outcome_eod=outcome_eod,
            llm_score=llm_score, llm_confidence=llm_conf,
            llm_reason=llm_reason, model_used=model_used,
        )

    print(f"\n  {'='*60}")
    print(f"  {ticker} backtest complete")
    print(f"  Total:    {total}  |  Skipped: {skipped}  |  "
          f"No reaction: {no_react}  |  Traded: {traded}")
    print(f"  {'='*60}")
    return traded


def _save_result(rns_id, ticker, timing, category,
                 ctx=None, react=None,
                 skipped_category=0, skipped_context=0,
                 would_trade=0, direction=None,
                 entry_price=None, entry_time=None,
                 prices=None, price_eod=None,
                 returns=None, return_eod=None,
                 outcome_t15=None, outcome_eod=None,
                 llm_score=None, llm_confidence=None,
                 llm_reason=None, model_used=None):
    ctx = ctx or {}; react = react or {}
    prices = prices or {}; returns = returns or {}
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO backtest_results (
            rns_id, ticker, timing, category, category_priority,
            skipped_category, price_position, above_sma20,
            ret5d, ret60d, pre_vol_ratio, setup_quality, skipped_context,
            reaction_triggered, reaction_strength, reaction_direction,
            reaction_confidence, reaction_price_chg,
            avg_vol_20d, immediate_vol, bars_found,
            would_trade, direction, entry_price, entry_time,
            price_t5, price_t15, price_t30, price_t60, price_eod,
            return_t5, return_t15, return_t30, return_t60, return_eod,
            outcome_t15, outcome_eod,
            model_used, llm_score, llm_confidence, llm_reason
        ) VALUES (
            :rns_id, :ticker, :timing, :category, :category_priority,
            :skipped_category, :price_position, :above_sma20,
            :ret5d, :ret60d, :pre_vol_ratio, :setup_quality, :skipped_context,
            :reaction_triggered, :reaction_strength, :reaction_direction,
            :reaction_confidence, :reaction_price_chg,
            :avg_vol_20d, :immediate_vol, :bars_found,
            :would_trade, :direction, :entry_price, :entry_time,
            :price_t5, :price_t15, :price_t30, :price_t60, :price_eod,
            :return_t5, :return_t15, :return_t30, :return_t60, :return_eod,
            :outcome_t15, :outcome_eod,
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
        would_trade=would_trade, direction=direction,
        entry_price=entry_price, entry_time=entry_time,
        price_t5=prices.get("t5"), price_t15=prices.get("t15"),
        price_t30=prices.get("t30"), price_t60=prices.get("t60"),
        price_eod=price_eod,
        return_t5=returns.get("t5"), return_t15=returns.get("t15"),
        return_t30=returns.get("t30"), return_t60=returns.get("t60"),
        return_eod=return_eod,
        outcome_t15=outcome_t15, outcome_eod=outcome_eod,
        model_used=model_used, llm_score=llm_score,
        llm_confidence=llm_confidence, llm_reason=llm_reason,
    ))
    conn.commit()
    conn.close()
