"""
End-to-end orchestrator flow test using mock Telegram objects and mocked LLM.

Simulates: /start → 30-question placement test → /study → story → 5 vocab lessons
→ 5 vocab quizzes → grammar lesson → grammar quiz → /add word → /stats
"""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("DEEPSEEK_API_KEY", "test")
os.environ.setdefault("TELEGRAM_CHAT_ID", "99")

# Counter ensures every callback_query gets a unique ID, preventing the
# orchestrator's double-tap deduplication set from swallowing repeat presses.
_cb_counter = 0


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch, tmp_path):
    global _cb_counter
    _cb_counter = 0

    db_path = str(tmp_path / "e2e.db")
    monkeypatch.setenv("DB_PATH", db_path)
    import importlib, config, db.schema, db.queries, core.session_store
    from agents import orchestrator
    importlib.reload(config)
    importlib.reload(db.schema)
    importlib.reload(db.queries)
    db.schema.run_migrations(db_path)
    core.session_store._cache.clear()
    orchestrator._seen_callbacks.clear()
    return db_path


USER_ID = 99
TODAY = date.today().isoformat()


def make_update(text: str, is_callback: bool = False) -> MagicMock:
    global _cb_counter
    update = MagicMock()
    user = MagicMock()
    user.id = USER_ID
    user.username = "testuser"
    user.first_name = "Test"

    if is_callback:
        _cb_counter += 1
        update.callback_query = MagicMock()
        update.callback_query.from_user = user
        update.callback_query.data = text
        update.callback_query.id = f"cb_{_cb_counter}"  # always unique
        update.callback_query.answer = AsyncMock()
        update.message = None
        update.effective_user = user
    else:
        update.callback_query = None
        update.message = MagicMock()
        update.message.text = text
        update.effective_user = user
    return update


def make_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()
    return ctx


def all_messages(ctx) -> list[str]:
    return [
        c.kwargs.get("text", c.args[1] if len(c.args) > 1 else "")
        for c in ctx.bot.send_message.call_args_list
    ]


# ── Placement test flow ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_triggers_placement():
    from agents.orchestrator import handle
    from core.state_machine import ConversationState
    from core import session_store

    ctx = make_ctx()
    await handle(make_update("/start"), ctx)

    msgs = all_messages(ctx)
    assert any("placement" in m.lower() or "30" in m for m in msgs)
    assert session_store.get(USER_ID).state == ConversationState.PLACEMENT_QUESTION


@pytest.mark.asyncio
async def test_placement_wrong_input_ignored():
    from agents.orchestrator import handle
    from core.state_machine import ConversationState
    from core import session_store

    ctx = make_ctx()
    await handle(make_update("/start"), ctx)
    msg_count = len(ctx.bot.send_message.call_args_list)

    await handle(make_update("hello"), ctx)
    assert len(ctx.bot.send_message.call_args_list) == msg_count
    assert session_store.get(USER_ID).state == ConversationState.PLACEMENT_QUESTION


@pytest.mark.asyncio
async def test_full_placement_test_completes():
    from agents.assessor import get_question
    from agents.orchestrator import handle
    from core.state_machine import ConversationState
    from core import session_store

    ctx = make_ctx()
    await handle(make_update("/start"), ctx)

    mock_level = {"level": "A2", "justification": "You know some basics."}
    with patch("agents.assessor.llm_call", new=AsyncMock(return_value=mock_level)):
        for i in range(30):
            q = get_question(i)
            await handle(make_update(q["correct"], is_callback=True), ctx)

    assert session_store.get(USER_ID).state == ConversationState.PLACEMENT_COMPLETE

    from db.queries import get_user
    user = get_user(USER_ID)
    assert user["cefr_level"] == "A2"
    assert user["placement_done"] == 1
    assert any("A2" in m for m in all_messages(ctx))


# ── Study session flow ────────────────────────────────────────────────────────

def _setup_user(level: str = "A1") -> None:
    from db.queries import upsert_user, set_user_level
    upsert_user(USER_ID, "testuser")
    set_user_level(USER_ID, level)


def _mock_vocab_batch(n: int = 20) -> dict:
    return {"items": [
        {"word": f"词{i}", "pinyin": f"cí{i}", "meaning": f"word{i}",
         "example_sent": f"Example {i}.", "mnemonic": f"mnemonic{i}"}
        for i in range(n)
    ]}


def _mock_grammar_batch(n: int = 10) -> dict:
    return {"items": [
        {"pattern": f"Pattern{i}", "explanation": "Explanation.", "example_sent": "Example."}
        for i in range(n)
    ]}


def _mock_story() -> dict:
    return {
        "story_text": "The dragon **词0** saw **词1**, **词2**, **词3**, and **词4**.",
        "story_hook": "But then something terrible happened...",
        "word_callbacks": {f"词{i}": f"story moment {i}" for i in range(5)},
    }


def _mock_quiz(correct: str = "A") -> dict:
    return {
        "question": "What does this mean?",
        "options": {"A": "correct", "B": "wrong1", "C": "wrong2", "D": "wrong3"},
        "correct": correct,
        "explanation": "Because A is right.",
    }


async def _run_study(ctx, vocab_patch=None, grammar_patch=None, story_patch=None):
    """Run /study with all three pool/story LLMs mocked."""
    from agents.orchestrator import handle
    vp = vocab_patch or _mock_vocab_batch()
    gp = grammar_patch or _mock_grammar_batch()
    sp = story_patch or _mock_story()
    with patch("agents.vocab_agent.llm_call", new=AsyncMock(return_value=vp)), \
         patch("agents.grammar_agent.llm_call", new=AsyncMock(return_value=gp)), \
         patch("agents.story_agent.llm_call", new=AsyncMock(return_value=sp)):
        await handle(make_update("/study"), ctx)


@pytest.mark.asyncio
async def test_study_shows_story():
    _setup_user("A1")
    from agents.orchestrator import handle
    from core.state_machine import ConversationState
    from core import session_store

    ctx = make_ctx()
    await _run_study(ctx)

    assert session_store.get(USER_ID).state == ConversationState.STORY_DISPLAY
    assert any("Story" in m or "词0" in m for m in all_messages(ctx))


@pytest.mark.asyncio
async def test_continue_after_story_starts_vocab():
    _setup_user("A1")
    from agents.orchestrator import handle
    from core.state_machine import ConversationState
    from core import session_store

    ctx = make_ctx()
    await _run_study(ctx)
    await handle(make_update("continue", is_callback=True), ctx)

    assert session_store.get(USER_ID).state == ConversationState.VOCAB_LESSON


@pytest.mark.asyncio
async def test_full_vocab_lesson_and_quiz_cycle():
    _setup_user("A1")
    from agents.orchestrator import handle
    from core.state_machine import ConversationState
    from core import session_store

    ctx = make_ctx()
    await _run_study(ctx)
    await handle(make_update("continue", is_callback=True), ctx)

    for _ in range(5):
        assert session_store.get(USER_ID).state == ConversationState.VOCAB_LESSON
        # got_it triggers quiz generation — mock the LLM call inside it
        with patch("agents.vocab_agent.llm_call", new=AsyncMock(return_value=_mock_quiz("B"))):
            await handle(make_update("got_it", is_callback=True), ctx)
        assert session_store.get(USER_ID).state == ConversationState.VOCAB_QUIZ
        await handle(make_update("A", is_callback=True), ctx)

    assert session_store.get(USER_ID).state == ConversationState.GRAMMAR_LESSON


@pytest.mark.asyncio
async def test_grammar_lesson_and_quiz():
    _setup_user("A1")
    from agents.orchestrator import handle
    from core.state_machine import ConversationState
    from core import session_store

    ctx = make_ctx()
    await _run_study(ctx)
    await handle(make_update("continue", is_callback=True), ctx)

    for _ in range(5):
        with patch("agents.vocab_agent.llm_call", new=AsyncMock(return_value=_mock_quiz("A"))):
            await handle(make_update("got_it", is_callback=True), ctx)
        await handle(make_update("A", is_callback=True), ctx)

    assert session_store.get(USER_ID).state == ConversationState.GRAMMAR_LESSON

    with patch("agents.grammar_agent.llm_call", new=AsyncMock(return_value=_mock_quiz("C"))):
        await handle(make_update("got_it", is_callback=True), ctx)
    assert session_store.get(USER_ID).state == ConversationState.GRAMMAR_QUIZ

    await handle(make_update("C", is_callback=True), ctx)
    assert session_store.get(USER_ID).state == ConversationState.IDLE


@pytest.mark.asyncio
async def test_srs_cards_created_after_full_session():
    _setup_user("A1")
    from agents.orchestrator import handle
    from db.queries import get_due_cards

    ctx = make_ctx()
    await _run_study(ctx)
    await handle(make_update("continue", is_callback=True), ctx)

    for _ in range(5):
        with patch("agents.vocab_agent.llm_call", new=AsyncMock(return_value=_mock_quiz("A"))):
            await handle(make_update("got_it", is_callback=True), ctx)
        await handle(make_update("A", is_callback=True), ctx)

    with patch("agents.grammar_agent.llm_call", new=AsyncMock(return_value=_mock_quiz("A"))):
        await handle(make_update("got_it", is_callback=True), ctx)
    await handle(make_update("A", is_callback=True), ctx)

    due = get_due_cards(USER_ID, TODAY)
    assert len(due) == 6  # 5 vocab + 1 grammar


# ── Review flow ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_review_flow_with_due_cards():
    _setup_user("A1")
    from agents.orchestrator import handle
    from db.queries import insert_vocab, create_srs_card
    from core.state_machine import ConversationState
    from core import session_store

    iid = insert_vocab(USER_ID, "山", "shān", "mountain", "山很高。", "mountains", "A1")
    create_srs_card(USER_ID, "vocab", iid, TODAY)

    ctx = make_ctx()
    await _run_study(ctx)

    mock_present = {"prompt": "What does 山 mean?", "answer": "mountain"}
    mock_eval = {"correct": True, "feedback": "Yes, 山 means mountain."}

    with patch("agents.review_agent.llm_call", new=AsyncMock(return_value=mock_present)):
        await handle(make_update("continue", is_callback=True), ctx)

    assert session_store.get(USER_ID).state == ConversationState.REVIEW_PROMPT

    with patch("agents.review_agent.llm_call", new=AsyncMock(return_value=mock_eval)):
        await handle(make_update("mountain"), ctx)

    assert session_store.get(USER_ID).state == ConversationState.REVIEW_ANSWER_SHOWN

    await handle(make_update("4", is_callback=True), ctx)
    assert session_store.get(USER_ID).state == ConversationState.VOCAB_LESSON


# ── /add command flow ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_vocab_flow():
    _setup_user("A1")
    from agents.orchestrator import handle
    from core.state_machine import ConversationState
    from core import session_store
    from db.queries import get_stats

    ctx = make_ctx()
    await handle(make_update("/add"), ctx)
    assert session_store.get(USER_ID).state == ConversationState.USER_ADD_VOCAB_WORD

    mock_enriched = {"word": "咖啡", "pinyin": "kāfēi", "meaning": "coffee",
                     "example_sent": "我喝咖啡。", "mnemonic": "sounds like café"}
    with patch("agents.vocab_agent.llm_call", new=AsyncMock(return_value=mock_enriched)):
        await handle(make_update("咖啡"), ctx)

    assert session_store.get(USER_ID).state == ConversationState.USER_ADD_VOCAB_CONFIRM
    assert any("咖啡" in m for m in all_messages(ctx))

    await handle(make_update("confirm_yes", is_callback=True), ctx)
    assert session_store.get(USER_ID).state == ConversationState.IDLE

    stats = get_stats(USER_ID, TODAY)
    assert stats["total_cards"] == 1
    assert stats["due_today"] == 1


@pytest.mark.asyncio
async def test_add_vocab_cancel():
    _setup_user("A1")
    from agents.orchestrator import handle
    from core.state_machine import ConversationState
    from core import session_store

    ctx = make_ctx()
    await handle(make_update("/add"), ctx)

    mock_enriched = {"word": "茶", "pinyin": "chá", "meaning": "tea",
                     "example_sent": "我喝茶。", "mnemonic": "CHA-rm of tea"}
    with patch("agents.vocab_agent.llm_call", new=AsyncMock(return_value=mock_enriched)):
        await handle(make_update("茶"), ctx)

    await handle(make_update("confirm_no", is_callback=True), ctx)
    assert session_store.get(USER_ID).state == ConversationState.IDLE


# ── /stats command ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stats_command():
    _setup_user("B1")
    from agents.orchestrator import handle

    ctx = make_ctx()
    await handle(make_update("/stats"), ctx)
    msgs = all_messages(ctx)
    assert any("B1" in m for m in msgs)
    assert any("cards" in m.lower() for m in msgs)


# ── Session persistence ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_session_persists_across_cache_clear():
    _setup_user("A1")
    from core.state_machine import ConversationState
    from core import session_store

    ctx = make_ctx()
    await _run_study(ctx)

    session_store._cache.clear()

    state = session_store.get(USER_ID)
    assert state.state == ConversationState.STORY_DISPLAY
