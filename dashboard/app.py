import sqlite3
from pathlib import Path
from flask import Flask, render_template, jsonify
from config.settings import DB_PATH

app = Flask(__name__)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_summary():
    conn = get_connection()

    total_rns = conn.execute(
        "SELECT COUNT(*) FROM rns_events WHERE ticker='MATD'"
    ).fetchone()[0]

    fetched_ok = conn.execute(
        "SELECT COUNT(*) FROM rns_events WHERE ticker='MATD' AND fetch_status='ok'"
    ).fetchone()[0]

    dates = conn.execute(
        "SELECT MIN(datetime), MAX(datetime) FROM rns_events WHERE ticker='MATD'"
    ).fetchone()
    rns_from = dates[0][:10] if dates[0] else "—"
    rns_to   = dates[1][:10] if dates[1] else "—"

    daily_bars = conn.execute(
        "SELECT COUNT(*) FROM price_bars WHERE ticker='MATD' AND interval='1d'"
    ).fetchone()[0]

    intraday_bars = conn.execute(
        "SELECT COUNT(*) FROM price_bars WHERE ticker='MATD' AND interval='5m'"
    ).fetchone()[0]

    price_dates = conn.execute(
        "SELECT MIN(datetime), MAX(datetime) FROM price_bars "
        "WHERE ticker='MATD' AND interval='1d'"
    ).fetchone()
    price_from = price_dates[0][:10] if price_dates[0] else "—"
    price_to   = price_dates[1][:10] if price_dates[1] else "—"

    intra_dates = conn.execute(
        "SELECT MIN(datetime), MAX(datetime) FROM price_bars "
        "WHERE ticker='MATD' AND interval='5m'"
    ).fetchone()
    intra_from = intra_dates[0][:16] if intra_dates[0] else "—"
    intra_to   = intra_dates[1][:16] if intra_dates[1] else "—"

    categories = conn.execute("""
        SELECT category, headlinename, COUNT(*) as n
        FROM rns_events WHERE ticker='MATD'
        GROUP BY category ORDER BY n DESC
    """).fetchall()

    recent = conn.execute("""
        SELECT id, datetime, category, headlinename, title,
               fetch_status, LENGTH(body_text) as body_len
        FROM rns_events WHERE ticker='MATD'
        ORDER BY datetime DESC LIMIT 15
    """).fetchall()

    backtest_count = conn.execute(
        "SELECT COUNT(*) FROM backtest_results"
    ).fetchone()[0]

    backtest_summary = None
    if backtest_count > 0:
        backtest_summary = conn.execute("""
            SELECT
                COUNT(*)                                          as total,
                SUM(would_trade)                                  as trades,
                SUM(CASE WHEN outcome_t15='WIN'  THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome_t15='LOSS' THEN 1 ELSE 0 END) as losses,
                ROUND(AVG(CASE WHEN would_trade=1 THEN return_eod END), 2) as avg_return,
                MIN(llm_score) as min_score,
                MAX(llm_score) as max_score
            FROM backtest_results
        """).fetchone()

    score_dist = []
    if backtest_count > 0:
        score_dist = conn.execute("""
            SELECT llm_score, COUNT(*) as n
            FROM backtest_results
            GROUP BY llm_score ORDER BY llm_score DESC
        """).fetchall()

    conn.close()

    return dict(
        total_rns        = total_rns,
        fetched_ok       = fetched_ok,
        rns_from         = rns_from,
        rns_to           = rns_to,
        daily_bars       = daily_bars,
        intraday_bars    = intraday_bars,
        price_from       = price_from,
        price_to         = price_to,
        intra_from       = intra_from,
        intra_to         = intra_to,
        categories       = [dict(r) for r in categories],
        recent           = [dict(r) for r in recent],
        backtest_count   = backtest_count,
        backtest_summary = dict(backtest_summary) if backtest_summary else None,
        score_dist       = [dict(r) for r in score_dist],
    )


@app.route("/")
def index():
    data = get_summary()
    return render_template("index.html", **data)


@app.route("/rns/<int:news_id>")
def rns_detail(news_id):
    conn = get_connection()

    event = conn.execute(
        "SELECT * FROM rns_events WHERE id=?", (news_id,)
    ).fetchone()

    if not event:
        conn.close()
        return jsonify({"error": "not found"}), 404

    prices = conn.execute("""
        SELECT datetime, close FROM price_bars
        WHERE ticker='MATD' AND interval='1d'
        ORDER BY datetime ASC
    """).fetchall()
    price_list = [(r["datetime"][:10], r["close"]) for r in prices]
    date_str   = event["datetime"][:10]

    def get_price_on_day(d):
        for dt, c in price_list:
            if dt >= d:
                return c
        return None

    def get_price_n_days(d, n):
        closes = [p[1] for p in price_list]
        dates  = [p[0] for p in price_list]
        for i, dt in enumerate(dates):
            if dt >= d:
                idx = i + n
                return closes[idx] if idx < len(closes) else None
        return None

    def pct(b, t):
        if b and t:
            return round((t - b) / b * 100, 2)
        return None

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
            "on_day": base,
            "next1":  next1,
            "next5":  next5,
            "next10": next10,
            "ret1":   pct(base, next1),
            "ret5":   pct(base, next5),
            "ret10":  pct(base, next10),
        },
        "backtest": dict(bt) if bt else None,
    })


@app.route("/chart-data")
def chart_data():
    conn = get_connection()

    prices = conn.execute("""
        SELECT datetime, open, high, low, close, volume
        FROM price_bars WHERE ticker='MATD' AND interval='1d'
        ORDER BY datetime ASC
    """).fetchall()

    events = conn.execute("""
        SELECT e.id, e.datetime, e.category, e.headlinename, e.title,
               e.fetch_status,
               p.close  as price_on_day,
               p.datetime as price_date,
               b.llm_score, b.llm_confidence, b.timing,
               b.would_trade, b.outcome_t15, b.return_eod
        FROM rns_events e
        LEFT JOIN price_bars p
            ON p.ticker='MATD' AND p.interval='1d'
            AND p.datetime=(
                SELECT MIN(p2.datetime) FROM price_bars p2
                WHERE p2.ticker='MATD' AND p2.interval='1d'
                AND p2.datetime >= SUBSTR(e.datetime,1,10)
            )
        LEFT JOIN backtest_results b ON b.rns_id = e.id
        WHERE e.ticker='MATD'
        ORDER BY e.datetime ASC
    """).fetchall()

    conn.close()

    cat_colors = {
        "DRL": "#ff4d4d",
        "UPD": "#4d9fff",
        "FR":  "#4dff91",
        "IR":  "#a8ff4d",
        "IOE": "#ff9f4d",
        "ROI": "#ff9f4d",
        "MSC": "#c84dff",
        "NRA": "#888888",
        "NOA": "#555555",
        "RAG": "#555555",
        "BOA": "#ffdd4d",
        "AGR": "#4dffee",
    }

    score_colors = {
        2: "#4caf7d", 1: "#a8d8a8", 0: "#888888",
        -1: "#f0a07a", -2: "#f07070",
    }

    return jsonify({
        "prices":       [dict(r) for r in prices],
        "events":       [dict(r) for r in events],
        "cat_colors":   cat_colors,
        "score_colors": score_colors,
    })


@app.route("/backtest-data")
def backtest_data():
    """All backtest results for the analysis tab."""
    conn = get_connection()

    results = conn.execute("""
        SELECT
            b.*,
            e.datetime, e.category, e.headlinename,
            e.title, e.id as event_id
        FROM backtest_results b
        JOIN rns_events e ON b.rns_id = e.id
        WHERE e.ticker = 'MATD'
        ORDER BY e.datetime ASC
    """).fetchall()

    # Score accuracy — for each score, what % went the right way
    score_accuracy = conn.execute("""
        SELECT
            llm_score,
            COUNT(*) as total,
            SUM(CASE WHEN return_eod > 0 AND llm_score > 0 THEN 1
                     WHEN return_eod < 0 AND llm_score < 0 THEN 1
                     ELSE 0 END) as correct,
            ROUND(AVG(return_eod), 2) as avg_eod,
            ROUND(AVG(return_t15), 2) as avg_t15,
            MIN(return_eod) as min_eod,
            MAX(return_eod) as max_eod
        FROM backtest_results
        WHERE return_eod IS NOT NULL AND llm_score != 0
        GROUP BY llm_score
        ORDER BY llm_score DESC
    """).fetchall()

    # Category accuracy
    cat_accuracy = conn.execute("""
        SELECT
            e.category,
            e.headlinename,
            COUNT(*) as total,
            ROUND(AVG(b.llm_score), 2) as avg_score,
            ROUND(AVG(b.return_eod), 2) as avg_eod,
            SUM(CASE WHEN b.return_eod > 0 AND b.llm_score > 0 THEN 1
                     WHEN b.return_eod < 0 AND b.llm_score < 0 THEN 1
                     ELSE 0 END) as correct
        FROM backtest_results b
        JOIN rns_events e ON b.rns_id = e.id
        WHERE e.ticker='MATD' AND b.return_eod IS NOT NULL
        GROUP BY e.category
        ORDER BY total DESC
    """).fetchall()

    # Timing accuracy
    timing_accuracy = conn.execute("""
        SELECT
            timing,
            COUNT(*) as total,
            ROUND(AVG(return_eod), 2) as avg_eod,
            SUM(CASE WHEN return_eod > 0 AND llm_score > 0 THEN 1
                     WHEN return_eod < 0 AND llm_score < 0 THEN 1
                     ELSE 0 END) as correct
        FROM backtest_results
        WHERE return_eod IS NOT NULL AND llm_score != 0
        GROUP BY timing
    """).fetchall()

    # Confidence accuracy
    conf_accuracy = conn.execute("""
        SELECT
            llm_confidence,
            COUNT(*) as total,
            ROUND(AVG(return_eod), 2) as avg_eod,
            SUM(CASE WHEN return_eod > 0 AND llm_score > 0 THEN 1
                     WHEN return_eod < 0 AND llm_score < 0 THEN 1
                     ELSE 0 END) as correct
        FROM backtest_results
        WHERE return_eod IS NOT NULL AND llm_score != 0
        GROUP BY llm_confidence
        ORDER BY
            CASE llm_confidence
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 3
            END
    """).fetchall()

    # Cumulative P&L for would-trade signals
    trades = conn.execute("""
        SELECT e.datetime, b.direction,
               b.return_eod, b.outcome_eod,
               b.return_t15, b.outcome_t15,
               b.llm_score, b.llm_confidence,
               e.title, e.category
        FROM backtest_results b
        JOIN rns_events e ON b.rns_id = e.id
        WHERE e.ticker='MATD' AND b.would_trade=1
        ORDER BY e.datetime ASC
    """).fetchall()

    # Build cumulative P&L series
    cum_pnl = []
    running = 0.0
    for t in trades:
        ret = t["return_eod"] or 0
        running += ret
        cum_pnl.append({
            "date":      t["datetime"][:10],
            "title":     t["title"],
            "direction": t["direction"],
            "return":    round(ret, 2),
            "cumulative": round(running, 2),
            "outcome":   t["outcome_eod"],
        })

    conn.close()

    return jsonify({
        "results":         [dict(r) for r in results],
        "score_accuracy":  [dict(r) for r in score_accuracy],
        "cat_accuracy":    [dict(r) for r in cat_accuracy],
        "timing_accuracy": [dict(r) for r in timing_accuracy],
        "conf_accuracy":   [dict(r) for r in conf_accuracy],
        "cum_pnl":         cum_pnl,
    })


@app.route("/health")
def health():
    return {"status": "ok", "port": 5001}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
