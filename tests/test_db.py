import os
import pytest
from datetime import date, timedelta

# Point DB at a temp file before importing anything that loads config
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("DEEPSEEK_API_KEY", "test")
os.environ.setdefault("TELEGRAM_CHAT_ID", "12345")


@pytest.fixture
def tmp_db(monkeypatch, tmp_path):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    import importlib, config, db.schema, db.queries
    importlib.reload(config)
    importlib.reload(db.schema)
    importlib.reload(db.queries)
    db.schema.run_migrations(db_path)
    return db_path


def test_upsert_and_get_user(tmp_db):
    from db.queries import upsert_user, get_user
    upsert_user(1001, "alice")
    row = get_user(1001)
    assert row["username"] == "alice"
    assert row["placement_done"] == 0


def test_set_user_level(tmp_db):
    from db.queries import upsert_user, set_user_level, get_user
    upsert_user(1002, "bob")
    set_user_level(1002, "B1")
    row = get_user(1002)
    assert row["cefr_level"] == "B1"
    assert row["placement_done"] == 1


def test_insert_and_select_vocab(tmp_db):
    from db.queries import upsert_user, insert_vocab, select_daily_vocab, get_vocab_pool_count
    upsert_user(1003, "carol")
    today = date.today().isoformat()
    for i in range(7):
        insert_vocab(1003, f"词{i}", f"cí{i}", f"word {i}", f"example {i}", f"mnemonic {i}", "A1")
    count = get_vocab_pool_count(1003, "A1", today)
    assert count == 7
    items = select_daily_vocab(1003, "A1", today, n=5)
    assert len(items) == 5


def test_vocab_pool_excludes_already_delivered(tmp_db):
    from db.queries import upsert_user, insert_vocab, log_daily_item, get_vocab_pool_count
    upsert_user(1004, "dave")
    today = date.today().isoformat()
    ids = []
    for i in range(5):
        iid = insert_vocab(1004, f"词{i}", f"cí{i}", f"word {i}", "", "", "A1")
        ids.append(iid)
    # Mark all as delivered
    for iid in ids:
        log_daily_item(1004, today, "vocab", iid)
    count = get_vocab_pool_count(1004, "A1", today)
    assert count == 0


def test_srs_card_create_and_update(tmp_db):
    from db.queries import upsert_user, insert_vocab, create_srs_card, get_due_cards, update_srs_card, get_card_by_id
    upsert_user(1005, "eve")
    iid = insert_vocab(1005, "水", "shuǐ", "water", "", "", "A1")
    today = date.today().isoformat()
    card_id = create_srs_card(1005, "vocab", iid, today)
    assert card_id is not None

    due = get_due_cards(1005, today)
    assert any(c["card_id"] == card_id for c in due)

    future = (date.today() + timedelta(days=6)).isoformat()
    update_srs_card(card_id, 6, 2.6, 2, future)
    card = get_card_by_id(card_id)
    assert card["interval"] == 6
    assert card["repetitions"] == 2
    assert card["due_date"] == future


def test_create_srs_card_is_idempotent(tmp_db):
    from db.queries import upsert_user, insert_vocab, create_srs_card
    upsert_user(1006, "frank")
    iid = insert_vocab(1006, "火", "huǒ", "fire", "", "", "A1")
    today = date.today().isoformat()
    create_srs_card(1006, "vocab", iid, today)
    create_srs_card(1006, "vocab", iid, today)  # duplicate, should not raise


def test_review_log(tmp_db):
    from db.queries import upsert_user, insert_vocab, create_srs_card, log_review
    upsert_user(1007, "grace")
    iid = insert_vocab(1007, "风", "fēng", "wind", "", "", "A1")
    today = date.today().isoformat()
    card_id = create_srs_card(1007, "vocab", iid, today)
    log_review(card_id, 4, 1, 6, 2.5, 2.6)


def test_session_save_and_load(tmp_db):
    from db.queries import upsert_user, save_session, load_session
    upsert_user(1008, "test")
    save_session(1008, "VOCAB_LESSON", {"foo": "bar"})
    row = load_session(1008)
    assert row["state"] == "VOCAB_LESSON"
    import json
    ctx = json.loads(row["context_json"])
    assert ctx["foo"] == "bar"
    # overwrite
    save_session(1008, "IDLE", {})
    row2 = load_session(1008)
    assert row2["state"] == "IDLE"


def test_daily_story_save_and_retrieve(tmp_db):
    from db.queries import upsert_user, save_daily_story, get_daily_story, get_last_story_hook
    upsert_user(1009, "henry")
    today = date.today().isoformat()
    save_daily_story(1009, today, "Once upon a time...", "To be continued...", [1, 2], 3)
    row = get_daily_story(1009, today)
    assert row["story_text"] == "Once upon a time..."
    assert row["story_hook"] == "To be continued..."
    hook = get_last_story_hook(1009)
    assert hook == "To be continued..."


def test_stats(tmp_db):
    from db.queries import upsert_user, insert_vocab, create_srs_card, get_stats
    upsert_user(1010, "iris")
    today = date.today().isoformat()
    iid = insert_vocab(1010, "土", "tǔ", "earth", "", "", "A1")
    create_srs_card(1010, "vocab", iid, today)
    s = get_stats(1010, today)
    assert s["total_cards"] == 1
    assert s["due_today"] == 1
