import sqlite3
from flask import Flask, render_template, jsonify, request
from config.settings import DB_PATH, TICKERS, DEFAULT_TICKER

app = Flask(__name__)


@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def get_summary(ticker=DEFAULT_TICKER):
    conn = get_connection()

    total_rns = conn.execute(
        "SELECT COUNT(*) FROM rns_events WHERE ticker=?", (ticker,)
    ).fetchone()[0]

    fetched_ok = conn.execute(
        "SELECT COUNT(*) FROM rns_events WHERE ticker=? AND fetch_status='ok'",
        (ticker,)
    ).fetchone()[0]

    dates = conn.execute(
        "SELECT MIN(datetime), MAX(datetime) FROM rns_events WHERE ticker=?",
        (ticker,)
    ).fetchone()
    rns_from = dates[0][:10] if dates[0] else "—"
    rns_to   = dates[1][:10] if dates[1] else "—"

    daily_bars = conn.execute(
        "SELECT COUNT(*) FROM price_bars WHERE ticker=? AND interval='1d'",
        (ticker,)
    ).fetchone()[0]

    intraday_bars = conn.execute(
        "SELECT COUNT(*) FROM price_bars WHERE ticker=? AND interval='5m'",
        (ticker,)
    ).fetchone()[0]

    price_dates = conn.execute(
        "SELECT MIN(datetime), MAX(datetime) FROM price_bars "
        "WHERE ticker=? AND interval='1d'", (ticker,)
    ).fetchone()
    price_from = price_dates[0][:10] if price_dates[0] else "—"
    price_to   = price_dates[1][:10] if price_dates[1] else "—"

    intra_dates = conn.execute(
        "SELECT MIN(datetime), MAX(datetime) FROM price_bars "
        "WHERE ticker=? AND interval='5m'", (ticker,)
    ).fetchone()
    intra_from = intra_dates[0][:16] if intra_dates[0] else "—"
    intra_to   = intra_dates[1][:16] if intra_dates[1] else "—"

    categories = conn.execute("""
        SELECT category, headlinename, COUNT(*) as n
        FROM rns_events WHERE ticker=?
        GROUP BY category ORDER BY n DESC
    """, (ticker,)).fetchall()

    recent = conn.execute("""
        SELECT e.id, e.datetime, e.category, e.headlinename, e.title,
               e.fetch_status,
               b.reaction_triggered, b.reaction_strength,
               b.reaction_direction, b.timing, b.setup_quality
        FROM rns_events e
        LEFT JOIN backtest_results b ON b.rns_id = e.id
        WHERE e.ticker=?
        ORDER BY e.datetime DESC LIMIT 15
    """, (ticker,)).fetchall()

    backtest_count = conn.execute(
        "SELECT COUNT(*) FROM backtest_results b "
        "JOIN rns_events e ON b.rns_id=e.id WHERE e.ticker=?",
        (ticker,)
    ).fetchone()[0]

    backtest_summary = None
    if backtest_count > 0:
        backtest_summary = conn.execute("""
            SELECT
                COUNT(*)                                                 as total,
                SUM(b.skipped_category)                                  as cat_skipped,
                SUM(b.skipped_context)                                   as ctx_skipped,
                SUM(CASE WHEN b.reaction_triggered=1 THEN 1 ELSE 0 END) as reactions,
                SUM(b.would_trade)                                       as trades,
                SUM(CASE WHEN b.outcome_eod='WIN'  THEN 1 ELSE 0 END)   as wins,
                SUM(CASE WHEN b.outcome_eod='LOSS' THEN 1 ELSE 0 END)   as losses,
                ROUND(AVG(CASE WHEN b.would_trade=1 THEN b.return_eod END),2) as avg_return,
                ROUND(AVG(CASE WHEN b.would_trade=1 THEN b.reaction_strength END),2) as avg_strength
            FROM backtest_results b
            JOIN rns_events e ON b.rns_id=e.id
            WHERE e.ticker=?
        """, (ticker,)).fetchone()

    all_tickers_stats = conn.execute("""
        SELECT e.ticker,
               COUNT(DISTINCT e.id)                                          as rns_count,
               SUM(b.would_trade)                                            as trades,
               SUM(CASE WHEN b.outcome_eod='WIN' THEN 1 ELSE 0 END)         as wins,
               ROUND(AVG(CASE WHEN b.would_trade=1 THEN b.return_eod END),2) as avg_return
        FROM rns_events e
        LEFT JOIN backtest_results b ON b.rns_id=e.id
        GROUP BY e.ticker
        ORDER BY trades DESC
    """).fetchall()

    conn.close()

    return dict(
        ticker            = ticker,
        ticker_name       = TICKERS.get(ticker, {}).get("name", ticker),
        tickers           = {k: v["name"] for k, v in TICKERS.items()},
        total_rns         = total_rns,
        fetched_ok        = fetched_ok,
        rns_from          = rns_from,
        rns_to            = rns_to,
        daily_bars        = daily_bars,
        intraday_bars     = intraday_bars,
        price_from        = price_from,
        price_to          = price_to,
        intra_from        = intra_from,
        intra_to          = intra_to,
        categories        = [dict(r) for r in categories],
        recent            = [dict(r) for r in recent],
        backtest_count    = backtest_count,
        backtest_summary  = dict(backtest_summary) if backtest_summary else None,
        all_tickers_stats = [dict(r) for r in all_tickers_stats],
    )


@app.route("/")
def index():
    ticker = request.args.get("ticker", DEFAULT_TICKER).upper()
    if ticker not in TICKERS:
        ticker = DEFAULT_TICKER
    return render_template("index.html", **get_summary(ticker))


@app.route("/rns/<int:news_id>")
def rns_detail(news_id):
    conn = get_connection()
    event = conn.execute(
        "SELECT * FROM rns_events WHERE id=?", (news_id,)
    ).fetchone()
    if not event:
        conn.close()
        return jsonify({"error": "not found"}), 404

    ticker = event["ticker"]
    prices = conn.execute("""
        SELECT datetime, close FROM price_bars
        WHERE ticker=? AND interval='1d'
        ORDER BY datetime ASC
    """, (ticker,)).fetchall()
    price_list = [(r["datetime"][:10], r["close"]) for r in prices]
    date_str   = event["datetime"][:10]

    def get_price_on_day(d):
        for dt, c in price_list:
            if dt >= d: return c
        return None

    def get_price_n_days(d, n):
        dates  = [p[0] for p in price_list]
        closes = [p[1] for p in price_list]
        for i, dt in enumerate(dates):
            if dt >= d:
                idx = i + n
                return closes[idx] if idx < len(closes) else None
        return None

    def pct(b, t):
        return round((t - b) / b * 100, 2) if b and t else None

    base   = get_price_on_day(date_str)
    next1  = get_price_n_days(date_str, 1)
    next5  = get_price_n_days(date_str, 5)
    next10 = get_price_n_days(date_str, 10)

    bt = conn.execute(
        "SELECT * FROM backtest_results WHERE rns_id=?", (news_id,)
    ).fetchone()
    conn.close()

    return jsonify({
        "id":           event["id"],
        "ticker":       event["ticker"],
        "rnsnumber":    event["rnsnumber"],
        "category":     event["category"],
        "headlinename": event["headlinename"],
        "title":        event["title"],
        "datetime":     event["datetime"],
        "body_text":    event["body_text"],
        "fetch_status": event["fetch_status"],
        "price": {
            "on_day": base,  "next1": next1,
            "next5":  next5, "next10": next10,
            "ret1": pct(base, next1), "ret5": pct(base, next5),
            "ret10": pct(base, next10),
        },
        "backtest": dict(bt) if bt else None,
    })


@app.route("/chart-data")
def chart_data():
    ticker = request.args.get("ticker", DEFAULT_TICKER).upper()
    try:
        conn = get_connection()

        prices = conn.execute("""
            SELECT datetime, open, high, low, close, volume
            FROM price_bars WHERE ticker=? AND interval='1d'
            ORDER BY datetime ASC
        """, (ticker,)).fetchall()

        events = conn.execute("""
            SELECT e.id, e.datetime, e.category, e.headlinename, e.title,
                   p.close  as price_on_day,
                   b.reaction_triggered, b.reaction_strength,
                   b.reaction_direction, b.reaction_confidence,
                   b.reaction_price_chg, b.timing,
                   b.setup_quality, b.would_trade,
                   b.outcome_eod, b.return_eod
            FROM rns_events e
            LEFT JOIN price_bars p
                ON p.ticker=? AND p.interval='1d'
                AND p.datetime=(
                    SELECT MIN(p2.datetime) FROM price_bars p2
                    WHERE p2.ticker=? AND p2.interval='1d'
                    AND p2.datetime >= SUBSTR(e.datetime,1,10)
                )
            LEFT JOIN backtest_results b ON b.rns_id = e.id
            WHERE e.ticker=?
            ORDER BY e.datetime ASC
        """, (ticker, ticker, ticker, ticker)).fetchall()
        conn.close()

        cat_colors = {
            "DRL":"#ff4d4d","UPD":"#4d9fff","FR":"#4dff91",
            "IR":"#a8ff4d","IOE":"#ff9f4d","ROI":"#ff9f4d",
            "MSC":"#c84dff","NRA":"#666666","NOA":"#444444",
            "RAG":"#444444","BOA":"#ffdd4d","AGR":"#4dffee",
        }
        return jsonify({
            "prices":     [dict(r) for r in prices],
            "events":     [dict(r) for r in events],
            "cat_colors": cat_colors,
            "ticker":     ticker,
        })
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/backtest-data")
def backtest_data():
    ticker = request.args.get("ticker", DEFAULT_TICKER).upper()
    try:
        conn = get_connection()

        results = conn.execute("""
            SELECT b.*, e.datetime, e.category, e.headlinename,
                   e.title, e.id as event_id
            FROM backtest_results b
            JOIN rns_events e ON b.rns_id = e.id
            WHERE e.ticker=?
            ORDER BY e.datetime ASC
        """, (ticker,)).fetchall()

        strength_buckets = conn.execute("""
            SELECT
                CASE
                    WHEN b.reaction_strength < 4  THEN '2-4x'
                    WHEN b.reaction_strength < 6  THEN '4-6x'
                    WHEN b.reaction_strength < 10 THEN '6-10x'
                    ELSE '10x+'
                END as bucket,
                COUNT(*) as total,
                SUM(CASE WHEN b.outcome_eod='WIN' THEN 1 ELSE 0 END) as wins,
                ROUND(AVG(b.return_eod),2) as avg_return
            FROM backtest_results b
            JOIN rns_events e ON b.rns_id=e.id
            WHERE e.ticker=? AND b.would_trade=1 AND b.return_eod IS NOT NULL
            GROUP BY bucket ORDER BY MIN(b.reaction_strength)
        """, (ticker,)).fetchall()

        timing_results = conn.execute("""
            SELECT b.timing,
                   COUNT(*) as total,
                   SUM(b.would_trade) as trades,
                   SUM(CASE WHEN b.outcome_eod='WIN' THEN 1 ELSE 0 END) as wins,
                   ROUND(AVG(CASE WHEN b.would_trade=1 THEN b.return_eod END),2) as avg_return
            FROM backtest_results b
            JOIN rns_events e ON b.rns_id=e.id
            WHERE e.ticker=?
            GROUP BY b.timing ORDER BY b.timing
        """, (ticker,)).fetchall()

        cat_results = conn.execute("""
            SELECT b.category,
                   COUNT(*) as total,
                   SUM(b.skipped_category) as skipped,
                   SUM(b.would_trade) as trades,
                   SUM(CASE WHEN b.outcome_eod='WIN' THEN 1 ELSE 0 END) as wins,
                   ROUND(AVG(CASE WHEN b.would_trade=1 THEN b.return_eod END),2) as avg_return,
                   ROUND(AVG(b.reaction_strength),2) as avg_strength
            FROM backtest_results b
            JOIN rns_events e ON b.rns_id=e.id
            WHERE e.ticker=?
            GROUP BY b.category ORDER BY trades DESC, total DESC
        """, (ticker,)).fetchall()

        setup_results = conn.execute("""
            SELECT b.setup_quality,
                   COUNT(*) as total,
                   SUM(b.would_trade) as trades,
                   SUM(CASE WHEN b.outcome_eod='WIN' THEN 1 ELSE 0 END) as wins,
                   ROUND(AVG(CASE WHEN b.would_trade=1 THEN b.return_eod END),2) as avg_return
            FROM backtest_results b
            JOIN rns_events e ON b.rns_id=e.id
            WHERE e.ticker=? AND b.setup_quality IS NOT NULL
            GROUP BY b.setup_quality
        """, (ticker,)).fetchall()

        trades = conn.execute("""
            SELECT e.datetime, b.direction, b.return_eod, b.return_t15,
                   b.outcome_eod, b.reaction_strength, b.reaction_price_chg,
                   e.title, e.category, b.entry_price
            FROM backtest_results b
            JOIN rns_events e ON b.rns_id = e.id
            WHERE e.ticker=? AND b.would_trade=1
            ORDER BY e.datetime ASC
        """, (ticker,)).fetchall()

        cum_pnl = []
        running = 0.0
        for t in trades:
            ret = t["return_eod"] or 0
            running += ret
            cum_pnl.append({
                "date":       t["datetime"][:10],
                "title":      t["title"],
                "category":   t["category"],
                "direction":  t["direction"],
                "return":     round(ret, 2),
                "cumulative": round(running, 2),
                "outcome":    t["outcome_eod"],
                "strength":   t["reaction_strength"],
                "price_chg":  t["reaction_price_chg"],
                "entry":      t["entry_price"],
            })

        strength_dist = conn.execute("""
            SELECT ROUND(b.reaction_strength,0) as s, COUNT(*) as n
            FROM backtest_results b
            JOIN rns_events e ON b.rns_id=e.id
            WHERE e.ticker=? AND b.reaction_strength > 0
            GROUP BY ROUND(b.reaction_strength,0)
            ORDER BY s ASC
        """, (ticker,)).fetchall()

        conn.close()

        return jsonify({
            "results":          [dict(r) for r in results],
            "strength_buckets": [dict(r) for r in strength_buckets],
            "timing_results":   [dict(r) for r in timing_results],
            "cat_results":      [dict(r) for r in cat_results],
            "setup_results":    [dict(r) for r in setup_results],
            "cum_pnl":          cum_pnl,
            "strength_dist":    [dict(r) for r in strength_dist],
            "ticker":           ticker,
        })
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok", "port": 5001})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
