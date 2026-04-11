import json
from datetime import datetime
from config.settings import (TICKER, HOLD_MINUTES,
                              TRADE_SCORE_THRESHOLD,
                              TRADE_CONFIDENCE_NEEDED)
from src.collect.database import get_connection
from src.collect.price_fetcher import (get_price_at,
                                        get_price_after_minutes,
                                        get_eod_price)
from src.score.scorer import score_rns

MARKET_OPEN_HOUR  = 8
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MIN  = 30


def is_market_hours(dt_str):
    """Return True if datetime is within UK market hours 08:00-16:30."""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", ""))
        mins = dt.hour * 60 + dt.minute
        return (MARKET_OPEN_HOUR * 60) <= mins <= (MARKET_CLOSE_HOUR * 60 + MARKET_CLOSE_MIN)
    except Exception:
        return False


def run_backtest(ticker=TICKER, dry_run=False):
    """
    Main backtest loop.
    Iterates all scored RNS events, gets prices, scores with LLM,
    calculates returns, saves results.
    dry_run=True skips writing to DB.
    """
    conn = get_connection()
    events = conn.execute("""
        SELECT * FROM rns_events
        WHERE ticker=? AND fetch_status='ok'
        ORDER BY datetime ASC
    """, (ticker,)).fetchall()
    conn.close()

    print(f"\nRunning backtest on {len(events)} events for {ticker}...")
    print("-" * 65)

    results = []
    for i, event in enumerate(events):
        news_id      = event["id"]
        dt_str       = event["datetime"]
        title        = event["title"] or ""
        category     = event["category"] or ""
        headlinename = event["headlinename"] or ""
        body_text    = event["body_text"] or ""

        print(f"\n[{i+1}/{len(events)}] {dt_str[:16]}  {category:<5} {title[:45]}")

        # Skip if no body text
        if not body_text:
            print("  SKIP: no body text")
            continue

        # Score with LLM
        scored = score_rns(
            ticker=ticker,
            company_name="Petro Matad Limited",
            category=category,
            headlinename=headlinename,
            title=title,
            body_text=body_text
        )
        if not scored:
            print("  SKIP: scoring failed")
            continue

        score      = int(scored.get("score", 0))
        confidence = scored.get("confidence", "low")
        reason     = scored.get("reason", "")
        print(f"  Score={score:+d}  Conf={confidence}  {reason[:55]}")

        # Determine entry time
        in_market  = is_market_hours(dt_str)
        entry_time = dt_str if in_market else dt_str[:10] + "T08:01:00"
        if not in_market:
            print(f"  Pre-market — entry at open: {entry_time}")

        # Get entry price
        bar = get_price_at(ticker, entry_time)
        if not bar:
            print(f"  SKIP: no price data near {entry_time}")
            continue
        entry_price = bar["open"]

        # Get outcome prices at each hold interval
        prices = {}
        for mins in HOLD_MINUTES:
            prices[f"t{mins}"] = get_price_after_minutes(
                ticker, entry_time, mins)
        prices["eod"] = get_eod_price(ticker, dt_str[:10])

        # Calculate returns (flip sign for SELL signals)
        sign = 1 if score >= 0 else -1
        returns = {}
        for key, price in prices.items():
            if price and entry_price:
                returns[key] = round(
                    (price - entry_price) / entry_price * 100 * sign, 4)
            else:
                returns[key] = None

        # Trade decision
        would_trade = (abs(score) >= TRADE_SCORE_THRESHOLD and
                       confidence == TRADE_CONFIDENCE_NEEDED)
        direction   = "BUY" if score > 0 else ("SELL" if score < 0 else "NONE")

        # Outcome
        ret_t15    = returns.get("t15")
        outcome_t15 = None
        if ret_t15 is not None and would_trade:
            outcome_t15 = "WIN" if ret_t15 > 0 else "LOSS"

        ret_eod    = returns.get("eod")
        outcome_eod = None
        if ret_eod is not None and would_trade:
            outcome_eod = "WIN" if ret_eod > 0 else "LOSS"

        t15_str = f"{prices.get('t15', '?') }p → {returns.get('t15', '?')  }%"
        print(f"  Entry={entry_price}p  T+15={t15_str}  "
              f"Trade={'YES → '+direction if would_trade else 'no'}"
              f"{' '+outcome_t15 if outcome_t15 else ''}")

        result = dict(
            rns_id         = news_id,
            llm_score      = score,
            llm_confidence = confidence,
            llm_reason     = reason,
            llm_raw        = json.dumps(scored),
            entry_price    = entry_price,
            entry_time     = entry_time,
            price_t5       = prices.get("t5"),
            price_t15      = prices.get("t15"),
            price_t30      = prices.get("t30"),
            price_t60      = prices.get("t60"),
            price_eod      = prices.get("eod"),
            return_t5      = returns.get("t5"),
            return_t15     = returns.get("t15"),
            return_t30     = returns.get("t30"),
            return_t60     = returns.get("t60"),
            return_eod     = returns.get("eod"),
            would_trade    = 1 if would_trade else 0,
            direction      = direction,
            outcome_t15    = outcome_t15,
            outcome_eod    = outcome_eod,
        )
        results.append(result)

        if not dry_run:
            _save_result(result)

    print("\n" + "-" * 65)
    print(f"Backtest complete. {len(results)} events processed.")
    tradeable = [r for r in results if r["would_trade"]]
    wins = [r for r in tradeable if r["outcome_t15"] == "WIN"]
    print(f"Trade signals: {len(tradeable)}  |  Wins at T+15: {len(wins)}"
          f"  |  Win rate: {len(wins)/len(tradeable)*100:.0f}%"
          if tradeable else "No trade signals generated.")
    return results


def _save_result(result):
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO backtest_results
        (rns_id, llm_score, llm_confidence, llm_reason, llm_raw,
         entry_price, entry_time,
         price_t5, price_t15, price_t30, price_t60, price_eod,
         return_t5, return_t15, return_t30, return_t60, return_eod,
         would_trade, direction, outcome_t15, outcome_eod)
        VALUES
        (:rns_id, :llm_score, :llm_confidence, :llm_reason, :llm_raw,
         :entry_price, :entry_time,
         :price_t5, :price_t15, :price_t30, :price_t60, :price_eod,
         :return_t5, :return_t15, :return_t30, :return_t60, :return_eod,
         :would_trade, :direction, :outcome_t15, :outcome_eod)
    """, result)
    conn.commit()
    conn.close()
