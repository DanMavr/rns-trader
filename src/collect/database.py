import sqlite3
from pathlib import Path
from config.settings import DB_PATH


def get_connection():
    """Return a SQLite connection with Row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they do not already exist."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS rns_events (
            id              INTEGER PRIMARY KEY,
            ticker          TEXT NOT NULL,
            rnsnumber       TEXT,
            category        TEXT,
            headlinename    TEXT,
            title           TEXT,
            body_html       TEXT,
            body_text       TEXT,
            datetime        TEXT,
            is_market_hours INTEGER DEFAULT 0,
            fetch_status    TEXT DEFAULT 'pending'
        );

        CREATE TABLE IF NOT EXISTS price_bars (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker    TEXT NOT NULL,
            datetime  TEXT NOT NULL,
            interval  TEXT NOT NULL,
            open      REAL,
            high      REAL,
            low       REAL,
            close     REAL,
            volume    INTEGER,
            UNIQUE(ticker, datetime, interval)
        );

        CREATE TABLE IF NOT EXISTS backtest_results (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            rns_id           INTEGER REFERENCES rns_events(id),
            llm_score        INTEGER,
            llm_confidence   TEXT,
            llm_reason       TEXT,
            llm_raw          TEXT,
            entry_price      REAL,
            entry_time       TEXT,
            price_t5         REAL,
            price_t15        REAL,
            price_t30        REAL,
            price_t60        REAL,
            price_eod        REAL,
            return_t5        REAL,
            return_t15       REAL,
            return_t30       REAL,
            return_t60       REAL,
            return_eod       REAL,
            would_trade      INTEGER DEFAULT 0,
            direction        TEXT,
            outcome_t15      TEXT,
            outcome_eod      TEXT
        );
    """)
    conn.commit()
    conn.close()
    print(f"  Database initialised at {DB_PATH}")


if __name__ == "__main__":
    init_db()
