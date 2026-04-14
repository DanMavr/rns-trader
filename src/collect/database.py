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
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            rns_id              INTEGER NOT NULL UNIQUE,
            ticker              TEXT    NOT NULL,
            timing              TEXT,
            category            TEXT,
            category_priority   TEXT,
            skipped_category    INTEGER DEFAULT 0,
            price_position      REAL,
            above_sma20         INTEGER,
            ret5d               REAL,
            ret60d              REAL,
            pre_vol_ratio       REAL,
            setup_quality       TEXT,
            skipped_context     INTEGER DEFAULT 0,
            reaction_triggered  INTEGER DEFAULT 0,
            reaction_strength   REAL,
            reaction_direction  INTEGER,
            reaction_confidence REAL,
            reaction_price_chg  REAL,
            avg_vol_20d         REAL,
            immediate_vol       REAL,
            bars_found          INTEGER,
            reaction_date       TEXT,
            would_trade         INTEGER DEFAULT 0,
            direction           TEXT,
            entry_price         REAL,
            entry_time          TEXT,
            price_t1d           REAL,
            price_t5d           REAL,
            price_t20d          REAL,
            return_t1d          REAL,
            return_t5d          REAL,
            return_t20d         REAL,
            outcome_t1d         TEXT,
            outcome_t5d         TEXT,
            outcome_t20d        TEXT,
            model_used          TEXT,
            llm_score           INTEGER,
            llm_confidence      TEXT,
            llm_reason          TEXT,
            created_at          TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (rns_id) REFERENCES rns_events(id)
        );

        CREATE INDEX IF NOT EXISTS idx_rns_ticker_dt
            ON rns_events(ticker, datetime);
        CREATE INDEX IF NOT EXISTS idx_price_ticker_interval_dt
            ON price_bars(ticker, interval, datetime);
        CREATE INDEX IF NOT EXISTS idx_backtest_rns
            ON backtest_results(rns_id);
        CREATE INDEX IF NOT EXISTS idx_backtest_ticker
            ON backtest_results(ticker);
        CREATE INDEX IF NOT EXISTS idx_backtest_reaction
            ON backtest_results(reaction_triggered, reaction_strength);
    """)
    conn.commit()
    conn.close()
    print(f"  Database initialised at {DB_PATH}")
