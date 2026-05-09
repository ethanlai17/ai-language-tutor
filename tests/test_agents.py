"""
Mock-based tests for all agents. No real API calls are made.
"""
import os
import pytest
from unittest.mock import AsyncMock, patch
from datetime import date

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("DEEPSEEK_API_KEY", "test")
os.environ.setdefault("TELEGRAM_CHAT_ID", "12345")


@pytest.fixture(autouse=True)
def tmp_db(monkeypatch, tmp_path):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    import importlib, config, db.schema, db.queries
    importlib.reload(config)
    importlib.reload(db.schema)
    importlib.reload(db.queries)
    db.schema.run_migrations(db_path)
    from db.queries import upsert_user, set_user_level
    upsert_user(99, "testuser")
    set_user_level(99, "A1")
    return db_path


# ── Assessor ──────────────────────────────────────────────────────────────────

def test_assessor_loads_30_questions():
    from agents.assessor import total_questions, get_question
    assert total_questions() == 30
    q = get_question(0)
    assert "question" in q
    assert "options" in q
    assert q["correct"] in ("A", "B", "C", "D")


def test_assessor_score_answer():
    from agents.assessor import get_question, score_answer
    q = get_question(0)
    assert score_answer(q, q["correct"]) is True
    wrong = "D" if q["correct"] != "D" else "A"
    assert score_answer(q, wrong) is False


@pytest.mark.asyncio
async def test_assessor_determine_level():
    from agents.assessor import determine_level
    mock_result = {"level": "B1", "justification": "You scored well on B1 items."}
    with patch("agents.assessor.llm_call", new=AsyncMock(return_value=mock_result)):
        result = await determine_level({"A1": 5, "A2": 4, "B1": 3, "B2": 1, "C1": 0, "C2": 0})
    assert result["level"] == "B1"


# ── Vocab agent ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_vocab_agent_get_daily_vocab_seeds_pool():
    from agents.vocab_agent import get_daily_vocab
    today = date.today().isoformat()

    mock_batch = {"items": [
        {"word": f"词{i}", "pinyin": f"cí{i}", "meaning": f"word{i}",
         "example_sent": "ex", "mnemonic": "mn"}
        for i in range(20)
    ]}
    with patch("agents.vocab_agent.llm_call", new=AsyncMock(return_value=mock_batch)):
        items = await get_daily_vocab(99, "A1", today)

    assert len(items) == 5


@pytest.mark.asyncio
async def test_vocab_agent_no_duplicate_daily_vocab():
    from agents.vocab_agent import get_daily_vocab
    from db.queries import insert_vocab, log_daily_item, get_vocab_pool_count
    today = date.today().isoformat()

    # Insert more than VOCAB_POOL_MIN so ensure_vocab_pool doesn't try to seed,
    # then mark them all as delivered so the pool is empty.
    for i in range(15):
        iid = insert_vocab(99, f"词{i}", f"cí{i}", f"word{i}", "ex", "mn", "A1")
        log_daily_item(99, today, "vocab", iid)

    assert get_vocab_pool_count(99, "A1", today) == 0

    # LLM mock returns nothing — pool stays empty
    with patch("agents.vocab_agent.llm_call", new=AsyncMock(return_value={"items": []})):
        items = await get_daily_vocab(99, "A1", today)
    assert len(items) == 0


@pytest.mark.asyncio
async def test_vocab_agent_enrich_user_word():
    from agents.vocab_agent import enrich_user_word
    mock = {"word": "咖啡", "pinyin": "kāfēi", "meaning": "coffee",
            "example_sent": "我喝咖啡。", "mnemonic": "Sounds like café"}
    with patch("agents.vocab_agent.llm_call", new=AsyncMock(return_value=mock)):
        result = await enrich_user_word("咖啡")
    assert result["word"] == "咖啡"
    assert result["meaning"] == "coffee"


@pytest.mark.asyncio
async def test_vocab_agent_generate_quiz():
    from db.queries import insert_vocab, get_vocab_by_id, get_known_vocab
    from agents.vocab_agent import generate_vocab_quiz
    iid = insert_vocab(99, "书", "shū", "book", "我看书。", "shoe=书", "A1")
    item = get_vocab_by_id(iid)
    known = get_known_vocab(99)

    mock_quiz = {"question": "What does 书 mean?",
                 "options": {"A": "book", "B": "pen", "C": "desk", "D": "chair"},
                 "correct": "A", "explanation": "书 means book."}
    with patch("agents.vocab_agent.llm_call", new=AsyncMock(return_value=mock_quiz)):
        quiz = await generate_vocab_quiz(item, known)
    assert quiz["correct"] == "A"


# ── Grammar agent ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_grammar_agent_get_daily_grammar_seeds_pool():
    from agents.grammar_agent import get_daily_grammar
    today = date.today().isoformat()

    mock_batch = {"items": [
        {"pattern": f"Pattern {i}", "explanation": "An explanation.", "example_sent": "example"}
        for i in range(10)
    ]}
    with patch("agents.grammar_agent.llm_call", new=AsyncMock(return_value=mock_batch)):
        item = await get_daily_grammar(99, "A1", today)
    assert item is not None
    assert "pattern" in item.keys()


@pytest.mark.asyncio
async def test_grammar_agent_generate_quiz():
    from db.queries import insert_grammar, get_grammar_by_id, get_known_vocab
    from agents.grammar_agent import generate_grammar_quiz
    gid = insert_grammar(99, "把 construction", "Moves object before verb.", "把书放下。", "A1")
    item = get_grammar_by_id(gid)
    known = get_known_vocab(99)

    mock_quiz = {"question": "Which is correct?",
                 "options": {"A": "把书放下", "B": "书把放下", "C": "放下把书", "D": "把放下书"},
                 "correct": "A", "explanation": "Object comes after 把."}
    with patch("agents.grammar_agent.llm_call", new=AsyncMock(return_value=mock_quiz)):
        quiz = await generate_grammar_quiz(item, known)
    assert quiz["correct"] == "A"


# ── Story agent ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_story_agent_generates_and_caches():
    from db.queries import insert_vocab, get_vocab_by_id, insert_grammar, get_grammar_by_id
    from agents.story_agent import generate_daily_story
    today = date.today().isoformat()

    vocab_ids = [insert_vocab(99, f"字{i}", "zì", f"char{i}", "", "", "A1") for i in range(5)]
    from db.queries import get_conn
    with get_conn() as conn:
        vocab_items = [conn.execute("SELECT * FROM vocab_items WHERE item_id=?", (iid,)).fetchone()
                       for iid in vocab_ids]
    gid = insert_grammar(99, "是…的", "Emphasises time/manner.", "他是昨天来的。", "A1")
    grammar_item = get_grammar_by_id(gid)

    mock_story = {
        "story_text": "Once, **字0** and **字1** met **字2** near a **字3** selling **字4**.",
        "story_hook": "But then something terrible happened...",
        "word_callbacks": {"字0": "met the merchant", "字1": "dropped the lantern"},
    }
    with patch("agents.story_agent.llm_call", new=AsyncMock(return_value=mock_story)) as mock_llm:
        result1 = await generate_daily_story(99, today, vocab_items, grammar_item)
        call_count = mock_llm.call_count

        # Second call should return cached result without calling LLM again
        result2 = await generate_daily_story(99, today, vocab_items, grammar_item)
        assert mock_llm.call_count == call_count  # no extra call

    assert "字0" in result1["story_text"]
    assert result1["story_hook"] == "But then something terrible happened..."


@pytest.mark.asyncio
async def test_story_agent_uses_previous_hook():
    from db.queries import insert_vocab, insert_grammar, get_grammar_by_id, save_daily_story
    from agents.story_agent import generate_daily_story
    from datetime import date, timedelta

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    today = date.today().isoformat()

    save_daily_story(99, yesterday, "Day 1 story.", "A volcano erupted!", [1], 1)

    vocab_ids = [insert_vocab(99, f"新{i}", "xīn", f"new{i}", "", "", "A1") for i in range(5)]
    from db.queries import get_conn
    with get_conn() as conn:
        vocab_items = [conn.execute("SELECT * FROM vocab_items WHERE item_id=?", (iid,)).fetchone()
                       for iid in vocab_ids]
    gid = insert_grammar(99, "Test pattern", "desc", "example", "A1")
    grammar_item = get_grammar_by_id(gid)

    captured_prompt = {}

    async def fake_llm(system, user):
        captured_prompt["user"] = user
        return {"story_text": "Continued story", "story_hook": "Next hook", "word_callbacks": {}}

    with patch("agents.story_agent.llm_call", new=fake_llm):
        await generate_daily_story(99, today, vocab_items, grammar_item)

    assert "A volcano erupted!" in captured_prompt["user"]


# ── Review agent ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_review_agent_present_vocab_card():
    from db.queries import insert_vocab, create_srs_card, get_card_by_id
    from agents.review_agent import present_review_card
    today = date.today().isoformat()
    iid = insert_vocab(99, "月", "yuè", "moon", "月亮很美。", "moon rock", "A1")
    card_id = create_srs_card(99, "vocab", iid, today)
    card = get_card_by_id(card_id)

    mock = {"prompt": "What does 月 mean?", "answer": "moon"}
    with patch("agents.review_agent.llm_call", new=AsyncMock(return_value=mock)):
        result = await present_review_card(card)
    assert result["prompt"] == "What does 月 mean?"


@pytest.mark.asyncio
async def test_review_agent_evaluate_answer():
    from agents.review_agent import evaluate_answer
    mock = {"correct": True, "feedback": "Correct! 月 means moon."}
    with patch("agents.review_agent.llm_call", new=AsyncMock(return_value=mock)):
        result = await evaluate_answer("What does 月 mean?", "moon", "moon")
    assert result["correct"] is True


def test_review_agent_process_rating_updates_card():
    from db.queries import insert_vocab, create_srs_card, get_card_by_id
    from agents.review_agent import process_rating
    today = date.today().isoformat()
    iid = insert_vocab(99, "星", "xīng", "star", "星星很亮。", "star fish", "A1")
    card_id = create_srs_card(99, "vocab", iid, today)

    process_rating(card_id, 4)  # Easy
    card = get_card_by_id(card_id)
    assert card["interval"] == 1  # first rep = 1 day
    assert card["repetitions"] == 1

    process_rating(card_id, 3)  # Good
    card = get_card_by_id(card_id)
    assert card["interval"] == 6  # second rep = 6 days


def test_review_agent_process_rating_failure_resets():
    from db.queries import insert_vocab, create_srs_card, update_srs_card, get_card_by_id
    from agents.review_agent import process_rating
    from datetime import timedelta
    today = date.today().isoformat()
    iid = insert_vocab(99, "云", "yún", "cloud", "云很白。", "cloud computing", "A1")
    card_id = create_srs_card(99, "vocab", iid, today)
    future = (date.today() + timedelta(days=6)).isoformat()
    update_srs_card(card_id, 6, 2.5, 2, future)

    process_rating(card_id, 1)  # No idea
    card = get_card_by_id(card_id)
    assert card["interval"] == 1
    assert card["repetitions"] == 0
