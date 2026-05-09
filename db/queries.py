import json
import sqlite3
from datetime import date
from typing import Optional
from db.schema import get_conn


# ── Users ──────────────────────────────────────────────────────────────────

def upsert_user(user_id: int, username: str) -> None:
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO users(user_id, username, last_active)
            VALUES(?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                last_active = datetime('now')
        """, (user_id, username))


def get_user(user_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()


def set_user_level(user_id: int, level: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET cefr_level = ?, placement_done = 1 WHERE user_id = ?",
            (level, user_id)
        )


# ── Vocab ───────────────────────────────────────────────────────────────────

def insert_vocab(user_id: int, word: str, pinyin: str, meaning: str,
                 example_sent: str, mnemonic: str, cefr_level: str,
                 source: str = "system") -> int:
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO vocab_items(user_id, word, pinyin, meaning, example_sent, mnemonic, cefr_level, source)
            VALUES(?,?,?,?,?,?,?,?)
        """, (user_id, word, pinyin, meaning, example_sent, mnemonic, cefr_level, source))
        return cur.lastrowid


def get_vocab_pool_count(user_id: int, cefr_level: str, today: str) -> int:
    with get_conn() as conn:
        row = conn.execute("""
            SELECT COUNT(*) as cnt FROM vocab_items v
            WHERE v.user_id = ?
              AND v.cefr_level = ?
              AND NOT EXISTS (
                  SELECT 1 FROM daily_log dl
                  WHERE dl.user_id = v.user_id
                    AND dl.item_type = 'vocab'
                    AND dl.item_id = v.item_id
              )
        """, (user_id, cefr_level)).fetchone()
        return row["cnt"]


def select_daily_vocab(user_id: int, cefr_level: str, today: str, n: int = 5) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("""
            SELECT v.* FROM vocab_items v
            WHERE v.user_id = ?
              AND v.cefr_level = ?
              AND NOT EXISTS (
                  SELECT 1 FROM daily_log dl
                  WHERE dl.user_id = v.user_id
                    AND dl.item_type = 'vocab'
                    AND dl.item_id = v.item_id
              )
            ORDER BY RANDOM()
            LIMIT ?
        """, (user_id, cefr_level, n)).fetchall()


def get_vocab_by_id(item_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM vocab_items WHERE item_id = ?", (item_id,)).fetchone()


def get_vocab_by_ids(item_ids: list[int]) -> list[sqlite3.Row]:
    if not item_ids:
        return []
    placeholders = ",".join("?" * len(item_ids))
    with get_conn() as conn:
        return conn.execute(
            f"SELECT * FROM vocab_items WHERE item_id IN ({placeholders})",
            item_ids
        ).fetchall()


def get_known_vocab(user_id: int, limit: int = 20) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("""
            SELECT v.* FROM vocab_items v
            JOIN srs_cards s ON s.item_id = v.item_id AND s.item_type = 'vocab' AND s.user_id = v.user_id
            WHERE v.user_id = ?
            ORDER BY s.introduced_at DESC
            LIMIT ?
        """, (user_id, limit)).fetchall()


# ── Grammar ─────────────────────────────────────────────────────────────────

def insert_grammar(user_id: int, pattern: str, explanation: str,
                   example_sent: str, cefr_level: str, source: str = "system") -> int:
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO grammar_items(user_id, pattern, explanation, example_sent, cefr_level, source)
            VALUES(?,?,?,?,?,?)
        """, (user_id, pattern, explanation, example_sent, cefr_level, source))
        return cur.lastrowid


def get_grammar_pool_count(user_id: int, cefr_level: str) -> int:
    with get_conn() as conn:
        row = conn.execute("""
            SELECT COUNT(*) as cnt FROM grammar_items g
            WHERE g.user_id = ?
              AND g.cefr_level = ?
              AND NOT EXISTS (
                  SELECT 1 FROM daily_log dl
                  WHERE dl.user_id = g.user_id
                    AND dl.item_type = 'grammar'
                    AND dl.item_id = g.item_id
              )
        """, (user_id, cefr_level)).fetchone()
        return row["cnt"]


def select_daily_grammar(user_id: int, cefr_level: str, today: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("""
            SELECT g.* FROM grammar_items g
            WHERE g.user_id = ?
              AND g.cefr_level = ?
              AND NOT EXISTS (
                  SELECT 1 FROM daily_log dl
                  WHERE dl.user_id = g.user_id
                    AND dl.item_type = 'grammar'
                    AND dl.item_id = g.item_id
              )
            ORDER BY RANDOM()
            LIMIT 1
        """, (user_id, cefr_level)).fetchone()


def get_grammar_by_id(item_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM grammar_items WHERE item_id = ?", (item_id,)).fetchone()


# ── SRS Cards ───────────────────────────────────────────────────────────────

def create_srs_card(user_id: int, item_type: str, item_id: int, due_date: str) -> int:
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT OR IGNORE INTO srs_cards(user_id, item_type, item_id, due_date)
            VALUES(?,?,?,?)
        """, (user_id, item_type, item_id, due_date))
        return cur.lastrowid


def get_due_cards(user_id: int, today: str) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("""
            SELECT * FROM srs_cards
            WHERE user_id = ? AND due_date <= ?
            ORDER BY due_date ASC
        """, (user_id, today)).fetchall()


def update_srs_card(card_id: int, interval: int, ease_factor: float,
                    repetitions: int, due_date: str) -> None:
    with get_conn() as conn:
        conn.execute("""
            UPDATE srs_cards
            SET interval = ?, ease_factor = ?, repetitions = ?,
                due_date = ?, last_reviewed = datetime('now')
            WHERE card_id = ?
        """, (interval, ease_factor, repetitions, due_date, card_id))


def get_card_by_id(card_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM srs_cards WHERE card_id = ?", (card_id,)).fetchone()


def log_review(card_id: int, quality: int, interval_before: int,
               interval_after: int, ease_before: float, ease_after: float) -> None:
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO review_log(card_id, quality, interval_before, interval_after, ease_before, ease_after)
            VALUES(?,?,?,?,?,?)
        """, (card_id, quality, interval_before, interval_after, ease_before, ease_after))


# ── Daily Log ───────────────────────────────────────────────────────────────

def log_daily_item(user_id: int, log_date: str, item_type: str, item_id: int) -> None:
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO daily_log(user_id, log_date, item_type, item_id)
            VALUES(?,?,?,?)
        """, (user_id, log_date, item_type, item_id))


# ── Sessions ────────────────────────────────────────────────────────────────

def save_session(user_id: int, state: str, context: dict) -> None:
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO sessions(user_id, state, context_json, updated_at)
            VALUES(?, ?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                state = excluded.state,
                context_json = excluded.context_json,
                updated_at = datetime('now')
        """, (user_id, state, json.dumps(context)))


def load_session(user_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM sessions WHERE user_id = ?", (user_id,)).fetchone()


# ── Daily Stories ───────────────────────────────────────────────────────────

def save_daily_story(user_id: int, log_date: str, story_text: str,
                     story_hook: str, vocab_ids: list[int], grammar_id: int) -> None:
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO daily_stories(user_id, log_date, story_text, story_hook, vocab_ids, grammar_id)
            VALUES(?,?,?,?,?,?)
        """, (user_id, log_date, story_text, story_hook, json.dumps(vocab_ids), grammar_id))


def get_daily_story(user_id: int, log_date: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM daily_stories WHERE user_id = ? AND log_date = ?",
            (user_id, log_date)
        ).fetchone()


def get_last_story_hook(user_id: int) -> Optional[str]:
    with get_conn() as conn:
        row = conn.execute("""
            SELECT story_hook FROM daily_stories
            WHERE user_id = ?
            ORDER BY log_date DESC
            LIMIT 1
        """, (user_id,)).fetchone()
        return row["story_hook"] if row else None


# ── Stats ───────────────────────────────────────────────────────────────────

def get_stats(user_id: int, today: str) -> dict:
    with get_conn() as conn:
        total_cards = conn.execute(
            "SELECT COUNT(*) as n FROM srs_cards WHERE user_id = ?", (user_id,)
        ).fetchone()["n"]

        due_today = conn.execute(
            "SELECT COUNT(*) as n FROM srs_cards WHERE user_id = ? AND due_date <= ?",
            (user_id, today)
        ).fetchone()["n"]

        total_reviews = conn.execute(
            "SELECT COUNT(*) as n FROM review_log rl JOIN srs_cards s ON s.card_id = rl.card_id WHERE s.user_id = ?",
            (user_id,)
        ).fetchone()["n"]

        user = conn.execute("SELECT cefr_level FROM users WHERE user_id = ?", (user_id,)).fetchone()

        return {
            "cefr_level": user["cefr_level"] if user else "N/A",
            "total_cards": total_cards,
            "due_today": due_today,
            "total_reviews": total_reviews,
        }
