"""
Backtest simulator — reaction-based approach.

Pipeline for each RNS event:
  1. Category filter  — skip routine admin (NOA, RAG, BOA etc.)
  2. Context filter   — classify price setup (strong/neutral/extended/skip)
  3. Reaction detector — did volume AND price spike on RNS day?
  4. Record result    — save all measurements to backtest_results

Entry  : open price on reaction day
Exit   : close price on reaction day (EOD)
Return : (close - open) / open × 100, direction-adjusted

Optional LLM scoring via --llm flag (requires XAI_API_KEY in .env).
"""
from config.settings import TICKER, XAI_API_KEY
from src.collect.database import get_connection
from src.react.category_filter  import should_skip, get_priority
from src.react.context_filter   import get_price_context
from src.react.reaction_detector import detect_reaction, classify_timing


def get_eod_price(ticker: str, date_str: str) -> dict | None:
    """
    Fetch the 1d bar for an exact date.
    Uses exact date match — no >= to avoid returning next-day bars.
    date_str must be YYYY-MM-DD.
    """
    conn = get_connection()
    row = conn.execute("""
        SELECT * FROM price_bars
        WHERE ticker   = ?
          AND interval = '1d'
          AND SUBSTR(datetime, 1, 10) = ?
        LIMIT 1
    """, (ticker, date_str)).fetchone()
    conn.close()
    return dict(row) if row else None


def calc_return(entry: float, exit_price: float,
                direction: str = "BUY") -> float | None:
    """
    Calculate percentage return, direction-adjusted.
    BUY : positive if price went up
    SELL: positive if price went down
    Returns None if either price is missing or zero.
    """
    if not entry or not exit_price or entry == 0:
        return None
    sign = 1 if direction == "BUY" else -1
    return round((exit_price - entry) / entry * 100 * sign, 4)


def run_backtest(ticker: str = TICKER, use_llm: bool = False) -> int:
    """
    Run the full backtest for a single ticker.
    Processes all rns_events with fetch_status='ok' in chronological order.
    Returns the number of trades triggered.
    """
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

        # ── Step 1: Category filter ───────────────────────────────────────
        if should_skip(category):
            print(f"  SKIP: {category} (routine admin)\n")
            _save_result(rns_id, ticker, timing, category,
                         skipped_category=1)
            skipped += 1
            continue

        priority = get_priority(category)
        print(f"  Priority: {priority}  Timing: {timing}")

        # ── Step 2: Context filter ────────────────────────────────────────
        ctx = get_price_context(ticker, dt_str[:10])
        pos    = ctx.get('price_position')
        prevol = ctx.get('pre_vol_ratio')
        pos_str = f"{pos:.3f}" if pos is not None else "—"
        vol_str = f"{prevol:.2f}x" if prevol is not None else "—"
        print(f"  Setup: {ctx.get('setup_quality')}  Pos: {pos_str}  Pre-vol: {vol_str}")

        if ctx.get("skip"):
            print(f"  SKIP: momentum exhaustion (ret60d={ctx.get('ret60d')}%)\n")
            _save_result(rns_id, ticker, timing, category,
                         ctx=ctx, skipped_context=1)
            skipped += 1
            continue

        # ── Step 3: Reaction detector ─────────────────────────────────────
        react = detect_reaction(ticker, dt_str)
        print(f"  Vol: {react['immediate_vol']:.0f} vs "
              f"{react['avg_vol_20d']:.0f} avg "
              f"({react['strength']:.2f}x)  "
              f"Price(O->C): {react['price_change_pct']:+.2f}%  "
              f"Bars: {react['bars_found']}")

        if not react["triggered"]:
            print(f"  No reaction\n")
            _save_result(rns_id, ticker, timing, category,
                         ctx=ctx, react=react)
            no_react += 1
            continue

        # ── Reaction confirmed — record trade ─────────────────────────────
        direction   = "BUY" if react["direction"] == 1 else "SELL"
        entry_price = react["entry_price"]
        entry_time  = react["reaction_date"]   # YYYY-MM-DD

        print(f"  ✅ TRIGGERED {react['strength']:.2f}× | "
              f"{react['price_change_pct']:+.2f}% | "
              f"Conf: {react['confidence']:.2f} → {direction}")

        # EOD exit — same bar as reaction (close vs open)
        eod_bar    = get_eod_price(ticker, entry_time)
        price_eod  = eod_bar["close"] if eod_bar else None
        return_eod = calc_return(entry_price, price_eod, direction)
        outcome_eod = ("WIN"  if (return_eod or 0) > 0 else "LOSS") \
                       if return_eod is not None else None

        eod_str = f"{return_eod:+.4f}%" if return_eod is not None else "—"
        print(f"  Entry={entry_price:.4f}p  Close={price_eod}p  "
              f"EOD={eod_str}  {outcome_eod or '?'}\n")

        # ── Optional LLM scoring ──────────────────────────────────────────
        llm_score = llm_conf = llm_reason = model_used = None
        if use_llm and XAI_API_KEY:
            try:
                from src.score.scorer import score_rns
                from config.settings  import XAI_MODEL
                company_name = next(
                    (v["name"] for k, v in __import__(
                        "config.settings", fromlist=["TICKERS"]
                    ).TICKERS.items() if k == ticker),
                    ticker
                )
                scored = score_rns(
                    ticker=ticker,
                    company_name=company_name,
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
                    print(f"  [Grok] score={llm_score} conf={llm_conf} "
                          f"— {(llm_reason or '')[:60]}")
            except Exception as e:
                print(f"  [Grok] error: {e}")

        traded += 1
        _save_result(
            rns_id, ticker, timing, category,
            ctx=ctx, react=react,
            would_trade=1, direction=direction,
            entry_price=entry_price, entry_time=entry_time,
            price_eod=price_eod, return_eod=return_eod,
            outcome_eod=outcome_eod,
            llm_score=llm_score, llm_confidence=llm_conf,
            llm_reason=llm_reason, model_used=model_used,
        )

    print(f"\n  {'='*60}")
    print(f"  {ticker} backtest complete")
    print(f"  Total: {total}  |  Skipped: {skipped}  |  "
          f"No reaction: {no_react}  |  Traded: {traded}")
    print(f"  {'='*60}")
    return traded


def _save_result(
    rns_id:           int,
    ticker:           str,
    timing:           str,
    category:         str,
    ctx:              dict = None,
    react:            dict = None,
    skipped_category: int  = 0,
    skipped_context:  int  = 0,
    would_trade:      int  = 0,
    direction:        str  = None,
    entry_price:      float = None,
    entry_time:       str  = None,
    price_eod:        float = None,
    return_eod:       float = None,
    outcome_eod:      str  = None,
    llm_score:        int  = None,
    llm_confidence:   str  = None,
    llm_reason:       str  = None,
    model_used:       str  = None,
) -> None:
    """
    Persist a single backtest result to the database.
    Uses INSERT OR REPLACE on the UNIQUE(rns_id) constraint —
    re-running the backtest overwrites previous results cleanly.
    All T+15/30/60 columns are NULL in daily-bar mode (reserved
    for future intraday data).
    """
    ctx   = ctx   or {}
    react = react or {}
    conn  = get_connection()
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
            model_used, llm_score, llm_confidence, llm_reason,
            created_at
        ) VALUES (
            :rns_id, :ticker, :timing, :category, :category_priority,
            :skipped_category, :price_position, :above_sma20,
            :ret5d, :ret60d, :pre_vol_ratio, :setup_quality, :skipped_context,
            :reaction_triggered, :reaction_strength, :reaction_direction,
            :reaction_confidence, :reaction_price_chg,
            :avg_vol_20d, :immediate_vol, :bars_found,
            :would_trade, :direction, :entry_price, :entry_time,
            NULL, NULL, NULL, NULL, :price_eod,
            NULL, NULL, NULL, NULL, :return_eod,
            NULL, :outcome_eod,
            :model_used, :llm_score, :llm_confidence, :llm_reason,
            datetime('now')
        )
    """, dict(
        rns_id            = rns_id,
        ticker            = ticker,
        timing            = timing,
        category          = category,
        category_priority = get_priority(category),
        skipped_category  = skipped_category,
        price_position    = ctx.get("price_position"),
        above_sma20       = 1 if ctx.get("above_sma20") else 0,
        ret5d             = ctx.get("ret5d"),
        ret60d            = ctx.get("ret60d"),
        pre_vol_ratio     = ctx.get("pre_vol_ratio"),
        setup_quality     = ctx.get("setup_quality"),
        skipped_context   = skipped_context,
        reaction_triggered  = 1 if react.get("triggered") else 0,
        reaction_strength   = react.get("strength"),
        reaction_direction  = react.get("direction"),
        reaction_confidence = react.get("confidence"),
        reaction_price_chg  = react.get("price_change_pct"),
        avg_vol_20d         = react.get("avg_vol_20d"),
        immediate_vol       = react.get("immediate_vol"),
        bars_found          = react.get("bars_found"),
        would_trade         = would_trade,
        direction           = direction,
        entry_price         = entry_price,
        entry_time          = entry_time,
        price_eod           = price_eod,
        return_eod          = return_eod,
        outcome_eod         = outcome_eod,
        model_used          = model_used,
        llm_score           = llm_score,
        llm_confidence      = llm_confidence,
        llm_reason          = llm_reason,
    ))
    conn.commit()
    conn.close()
