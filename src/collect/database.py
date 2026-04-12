import sqlite3
from config.settings import DB_PATH


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS rns_events (
            id            INTEGER PRIMARY KEY,
            ticker        TEXT    NOT NULL,
            rnsnumber     TEXT,
            category      TEXT,
            headlinename  TEXT,
            title         TEXT,
            datetime      TEXT,
            url           TEXT,
            body_text     TEXT,
            fetch_status  TEXT    DEFAULT 'pending',
            timing        TEXT,
            created_at    TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS price_bars (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker    TEXT    NOT NULL,
            interval  TEXT    NOT NULL,
            datetime  TEXT    NOT NULL,
            open      REAL,
            high      REAL,
            low       REAL,
            close     REAL,
            volume    INTEGER,
            UNIQUE(ticker, interval, datetime)
        );

        CREATE TABLE IF NOT EXISTS backtest_results (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            rns_id         INTEGER NOT NULL,
            ticker         TEXT    NOT NULL,
            model_used     TEXT,
            timing         TEXT,
            llm_score      INTEGER,
            llm_confidence TEXT,
            llm_reason     TEXT,
            would_trade    INTEGER DEFAULT 0,
            direction      TEXT,
            entry_price    REAL,
            entry_time     TEXT,
            price_t5       REAL,
            price_t15      REAL,
            price_t30      REAL,
            price_t60      REAL,
            price_eod      REAL,
            return_t5      REAL,
            return_t15     REAL,
            return_t30     REAL,
            return_t60     REAL,
            return_eod     REAL,
            outcome_t15    TEXT,
            outcome_eod    TEXT,
            created_at     TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (rns_id) REFERENCES rns_events(id)
        );

        CREATE INDEX IF NOT EXISTS idx_rns_ticker_dt
            ON rns_events(ticker, datetime);
        CREATE INDEX IF NOT EXISTS idx_price_ticker_interval_dt
            ON price_bars(ticker, interval, datetime);
        CREATE INDEX IF NOT EXISTS idx_backtest_rns
            ON backtest_results(rns_id);
        CREATE INDEX IF NOT EXISTS idx_backtest_model
            ON backtest_results(model_used);
    """)
    conn.commit()
    conn.close()
    print(f"  Database initialised at {DB_PATH}")
