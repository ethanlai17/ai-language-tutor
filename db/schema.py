import sqlite3
from config import DB_PATH


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def run_migrations(db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            cefr_level  TEXT,
            placement_done INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now')),
            last_active TEXT
        );

        CREATE TABLE IF NOT EXISTS vocab_items (
            item_id     INTEGER PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(user_id),
            word        TEXT NOT NULL,
            pinyin      TEXT,
            meaning     TEXT NOT NULL,
            example_sent TEXT,
            mnemonic    TEXT,
            cefr_level  TEXT,
            source      TEXT DEFAULT 'system',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS grammar_items (
            item_id     INTEGER PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(user_id),
            pattern     TEXT NOT NULL,
            explanation TEXT,
            example_sent TEXT,
            cefr_level  TEXT,
            source      TEXT DEFAULT 'system',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS srs_cards (
            card_id         INTEGER PRIMARY KEY,
            user_id         INTEGER NOT NULL REFERENCES users(user_id),
            item_type       TEXT NOT NULL,
            item_id         INTEGER NOT NULL,
            interval        INTEGER DEFAULT 1,
            ease_factor     REAL DEFAULT 2.5,
            repetitions     INTEGER DEFAULT 0,
            due_date        TEXT,
            last_reviewed   TEXT,
            introduced_at   TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, item_type, item_id)
        );

        CREATE TABLE IF NOT EXISTS review_log (
            log_id          INTEGER PRIMARY KEY,
            card_id         INTEGER NOT NULL REFERENCES srs_cards(card_id),
            reviewed_at     TEXT DEFAULT (datetime('now')),
            quality         INTEGER,
            interval_before INTEGER,
            interval_after  INTEGER,
            ease_before     REAL,
            ease_after      REAL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            user_id     INTEGER PRIMARY KEY REFERENCES users(user_id),
            state       TEXT NOT NULL DEFAULT 'IDLE',
            context_json TEXT DEFAULT '{}',
            updated_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS daily_log (
            log_id      INTEGER PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(user_id),
            log_date    TEXT NOT NULL,
            item_type   TEXT NOT NULL,
            item_id     INTEGER NOT NULL,
            delivered_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, log_date, item_type, item_id)
        );

        CREATE TABLE IF NOT EXISTS daily_stories (
            story_id    INTEGER PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES users(user_id),
            log_date    TEXT NOT NULL,
            story_text  TEXT NOT NULL,
            story_hook  TEXT NOT NULL,
            vocab_ids   TEXT NOT NULL DEFAULT '[]',
            grammar_id  INTEGER,
            created_at  TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, log_date)
        );

        CREATE INDEX IF NOT EXISTS idx_srs_due ON srs_cards(user_id, due_date);
        CREATE INDEX IF NOT EXISTS idx_daily_log_date ON daily_log(user_id, log_date);
    """)

    conn.commit()
    conn.close()
