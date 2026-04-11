import sqlite3
from pathlib import Path
from flask import Flask, render_template
from config.settings import DB_PATH

app = Flask(__name__)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_summary():
    conn = get_connection()

    # RNS counts
    total_rns = conn.execute(
        "SELECT COUNT(*) FROM rns_events WHERE ticker='MATD'"
    ).fetchone()[0]

    fetched_ok = conn.execute(
        "SELECT COUNT(*) FROM rns_events WHERE ticker='MATD' AND fetch_status='ok'"
    ).fetchone()[0]

    # Date range of RNS
    dates = conn.execute(
        "SELECT MIN(datetime), MAX(datetime) FROM rns_events WHERE ticker='MATD'"
    ).fetchone()
    rns_from = dates[0][:10] if dates[0] else "—"
    rns_to   = dates[1][:10] if dates[1] else "—"

    # Price bar counts
    daily_bars = conn.execute(
        "SELECT COUNT(*) FROM price_bars WHERE ticker='MATD' AND interval='1d'"
    ).fetchone()[0]

    intraday_bars = conn.execute(
        "SELECT COUNT(*) FROM price_bars WHERE ticker='MATD' AND interval='5m'"
    ).fetchone()[0]

    # Price date range
    price_dates = conn.execute(
        "SELECT MIN(datetime), MAX(datetime) FROM price_bars WHERE ticker='MATD' AND interval='1d'"
    ).fetchone()
    price_from = price_dates[0][:10] if price_dates[0] else "—"
    price_to   = price_dates[1][:10] if price_dates[1] else "—"

    intra_dates = conn.execute(
        "SELECT MIN(datetime), MAX(datetime) FROM price_bars WHERE ticker='MATD' AND interval='5m'"
    ).fetchone()
    intra_from = intra_dates[0][:16] if intra_dates[0] else "—"
    intra_to   = intra_dates[1][:16] if intra_dates[1] else "—"

    # Category breakdown
    categories = conn.execute("""
        SELECT category, headlinename, COUNT(*) as n
        FROM rns_events
        WHERE ticker='MATD'
        GROUP BY category
        ORDER BY n DESC
    """).fetchall()

    # Recent announcements
    recent = conn.execute("""
        SELECT id, datetime, category, headlinename, title,
               fetch_status, LENGTH(body_text) as body_len
        FROM rns_events
        WHERE ticker='MATD'
        ORDER BY datetime DESC
        LIMIT 15
    """).fetchall()

    # Backtest results summary
    backtest_count = conn.execute(
        "SELECT COUNT(*) FROM backtest_results"
    ).fetchone()[0]

    backtest_summary = None
    if backtest_count > 0:
        backtest_summary = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(would_trade) as trades,
                SUM(CASE WHEN outcome_t15='WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome_t15='LOSS' THEN 1 ELSE 0 END) as losses,
                ROUND(AVG(CASE WHEN would_trade=1 THEN return_t15 END), 2) as avg_return,
                MIN(llm_score) as min_score,
                MAX(llm_score) as max_score
            FROM backtest_results
        """).fetchone()

    # Score distribution (if backtest run)
    score_dist = []
    if backtest_count > 0:
        score_dist = conn.execute("""
            SELECT llm_score, COUNT(*) as n
            FROM backtest_results
            GROUP BY llm_score
            ORDER BY llm_score DESC
        """).fetchall()

    conn.close()

    return dict(
        total_rns      = total_rns,
        fetched_ok     = fetched_ok,
        rns_from       = rns_from,
        rns_to         = rns_to,
        daily_bars     = daily_bars,
        intraday_bars  = intraday_bars,
        price_from     = price_from,
        price_to       = price_to,
        intra_from     = intra_from,
        intra_to       = intra_to,
        categories     = [dict(r) for r in categories],
        recent         = [dict(r) for r in recent],
        backtest_count = backtest_count,
        backtest_summary = dict(backtest_summary) if backtest_summary else None,
        score_dist     = [dict(r) for r in score_dist],
    )


@app.route("/")
def index():
    data = get_summary()
    return render_template("index.html", **data)


@app.route("/health")
def health():
    return {"status": "ok", "port": 5001}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
