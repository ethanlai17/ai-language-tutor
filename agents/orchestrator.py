from datetime import date, timedelta
from telegram import Update
from telegram.ext import ContextTypes

import agents.assessor as assessor
import agents.vocab_agent as vocab_agent
import agents.grammar_agent as grammar_agent
import agents.story_agent as story_agent
import agents.review_agent as review_agent
import agents.explanation_agent as explanation_agent
from bot import keyboards
from config import LEARNING_LANGUAGE
from core.state_machine import ConversationState as S, SessionState
from core import session_store
from db import queries

_seen_callbacks: set[str] = set()


async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query:
        cq = update.callback_query
        if cq.id in _seen_callbacks:
            await cq.answer()
            return
        _seen_callbacks.add(cq.id)
        if len(_seen_callbacks) > 2000:
            _seen_callbacks.clear()
        await cq.answer()
        user = cq.from_user
        text = cq.data
    else:
        user = update.effective_user
        text = (update.message.text or "").strip()

    chat_id = user.id
    queries.upsert_user(chat_id, user.username or user.first_name)

    state = session_store.get(chat_id)

    # Native Telegram reply to a bot message → forward to DeepSeek for explanation
    if (
        not update.callback_query
        and update.message
        and update.message.reply_to_message
        and update.message.reply_to_message.from_user
        and update.message.reply_to_message.from_user.id == ctx.bot.id
        and not text.startswith("/")
    ):
        bot_msg = update.message.reply_to_message.text or update.message.reply_to_message.caption or ""
        answer = await explanation_agent.explain(text, bot_msg, LEARNING_LANGUAGE)
        await _send(chat_id, answer, ctx)
        return

    # Command overrides
    if text == "/start":
        await _cmd_start(chat_id, state, ctx)
        return
    if text == "/study":
        await _cmd_session_config(chat_id, state, ctx, "study")
        return
    if text == "/add" or text.startswith("/add "):
        word_inline = text[len("/add "):].strip() if text.startswith("/add ") else ""
        await _cmd_add(chat_id, state, ctx, word_inline or None)
        return
    if text == "/stats":
        await _cmd_stats(chat_id, ctx)
        return
    if text == "/report":
        await _cmd_report(chat_id, state, ctx)
        return
    if text == "/review":
        await _cmd_session_config(chat_id, state, ctx, "review")
        return

    # State machine dispatch
    s = state.state
    if s == S.PLACEMENT_QUESTION:
        await _handle_placement_answer(chat_id, state, text, ctx)
    elif s == S.PLACEMENT_COMPLETE:
        await _cmd_session_config(chat_id, state, ctx, "study")
    elif s == S.STORY_DISPLAY:
        if text == "continue":
            await _start_lessons(chat_id, state, ctx)
    elif s == S.REVIEW_PROMPT:
        if text in ("A", "B", "C", "D"):
            await _handle_review_answer(chat_id, state, text, ctx)
    elif s == S.REVIEW_ANSWER_SHOWN:
        if text in ("1", "2", "3", "4"):
            await _handle_rating(chat_id, state, int(text), ctx)
    elif s == S.VOCAB_LESSON:
        if text == "got_it":
            await _send_vocab_quiz(chat_id, state, ctx)
    elif s == S.VOCAB_QUIZ:
        if text in ("A", "B", "C", "D"):
            await _handle_vocab_quiz_answer(chat_id, state, text, ctx)
    elif s == S.GRAMMAR_LESSON:
        if text == "got_it":
            await _send_grammar_quiz(chat_id, state, ctx)
    elif s == S.GRAMMAR_QUIZ:
        if text in ("A", "B", "C", "D"):
            await _handle_grammar_quiz_answer(chat_id, state, text, ctx)
    elif s == S.SESSION_CONFIG_TYPE:
        await _handle_config_type(chat_id, state, text, ctx)
    elif s == S.SESSION_CONFIG_VOCAB_COUNT:
        await _handle_config_vocab_count(chat_id, state, text, ctx)
    elif s == S.SESSION_CONFIG_GRAMMAR_COUNT:
        await _handle_config_grammar_count(chat_id, state, text, ctx)
    elif s == S.REPORT_PERIOD:
        await _handle_report_period(chat_id, state, text, ctx)
    elif s == S.REPORT_CUSTOM_DAYS:
        await _handle_report_custom_days(chat_id, state, text, ctx)
    elif s == S.REPORT_DETAIL:
        await _handle_report_detail(chat_id, state, text, ctx)
    elif s == S.USER_ADD_VOCAB_WORD:
        await _handle_add_word_input(chat_id, state, text, ctx)
    elif s == S.USER_ADD_VOCAB_CONFIRM:
        if text == "confirm_yes":
            await _handle_add_confirm(chat_id, state, ctx)
        elif text == "confirm_no":
            await _send(chat_id, "Cancelled. Send /add to try again.", ctx)
            state.state = S.IDLE
            session_store.save(chat_id, state)
    else:
        await _send(chat_id, "Send /study for today's lesson, /review to practise due cards, or /add to add a word.", ctx)


# ── Commands ─────────────────────────────────────────────────────────────────

async def _cmd_start(chat_id: int, state: SessionState, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_row = queries.get_user(chat_id)
    if user_row and user_row["placement_done"]:
        await _cmd_session_config(chat_id, state, ctx, "study")
        return

    await _send(chat_id,
        f"👋 Welcome to your {LEARNING_LANGUAGE} tutor!\n\n"
        "Before we start, I need to find your current level.\n"
        "You'll get <b>30 multiple-choice questions</b> across A1–C2.\n\n"
        "Let's go! 🚀",
        ctx, parse_mode="HTML"
    )
    state.state = S.PLACEMENT_QUESTION
    state.placement_index = 0
    state.placement_scores = {}
    session_store.save(chat_id, state)
    await _send_placement_question(chat_id, state, ctx)


async def _cmd_session_config(chat_id: int, state: SessionState, ctx: ContextTypes.DEFAULT_TYPE,
                              command: str) -> None:
    user_row = queries.get_user(chat_id)
    if not user_row or not user_row["placement_done"]:
        await _cmd_start(chat_id, state, ctx)
        return
    state.session_config_command = command
    state.session_config_type = None
    state.session_config_vocab_count = None
    state.session_config_grammar_count = None
    state.state = S.SESSION_CONFIG_TYPE
    session_store.save(chat_id, state)
    await _send(chat_id,
        "Vocabulary or grammar or both?\nType <code>v</code> for vocabulary, <code>g</code> for grammar, or <code>b</code> for both.",
        ctx, parse_mode="HTML"
    )


async def _handle_config_type(chat_id: int, state: SessionState, text: str,
                               ctx: ContextTypes.DEFAULT_TYPE) -> None:
    t = text.strip().lower()
    if t not in ("v", "g", "b"):
        await _send(chat_id, "Please type <code>v</code>, <code>g</code>, or <code>b</code>.", ctx, parse_mode="HTML")
        return
    state.session_config_type = t
    verb = "review" if state.session_config_command == "review" else "learn"
    if t in ("v", "b"):
        state.state = S.SESSION_CONFIG_VOCAB_COUNT
        session_store.save(chat_id, state)
        await _send(chat_id, f"How many words do you want to {verb} now? (or type <code>w</code> to let the bot decide)", ctx, parse_mode="HTML")
    else:
        state.state = S.SESSION_CONFIG_GRAMMAR_COUNT
        session_store.save(chat_id, state)
        await _send(chat_id, f"How many grammar points do you want to {verb} now? (or type <code>w</code> to let the bot decide)", ctx, parse_mode="HTML")


async def _handle_config_vocab_count(chat_id: int, state: SessionState, text: str,
                                      ctx: ContextTypes.DEFAULT_TYPE) -> None:
    n = _parse_count(text, default=3)
    if n is None:
        await _send(chat_id, "Please enter a number (e.g. 3) or <code>w</code> to let the bot decide.", ctx, parse_mode="HTML")
        return
    state.session_config_vocab_count = n
    if state.session_config_type == "b":
        verb = "review" if state.session_config_command == "review" else "learn"
        state.state = S.SESSION_CONFIG_GRAMMAR_COUNT
        session_store.save(chat_id, state)
        await _send(chat_id, f"How many grammar points do you want to {verb} now? (or type <code>w</code> to let the bot decide)", ctx, parse_mode="HTML")
    else:
        session_store.save(chat_id, state)
        await _execute_session_config(chat_id, state, ctx)


async def _handle_config_grammar_count(chat_id: int, state: SessionState, text: str,
                                        ctx: ContextTypes.DEFAULT_TYPE) -> None:
    n = _parse_count(text, default=1)
    if n is None:
        await _send(chat_id, "Please enter a number (e.g. 1) or <code>w</code> to let the bot decide.", ctx, parse_mode="HTML")
        return
    state.session_config_grammar_count = n
    session_store.save(chat_id, state)
    await _execute_session_config(chat_id, state, ctx)


def _parse_count(text: str, default: int) -> int | None:
    t = text.strip().lower()
    if t == "w":
        return default
    if t.isdigit() and 1 <= int(t) <= 20:
        return int(t)
    return None


async def _execute_session_config(chat_id: int, state: SessionState,
                                   ctx: ContextTypes.DEFAULT_TYPE) -> None:
    t = state.session_config_type
    vocab_n = state.session_config_vocab_count if t in ("v", "b") else 0
    grammar_n = state.session_config_grammar_count if t in ("g", "b") else 0
    if state.session_config_command == "study":
        await _run_study(chat_id, state, ctx, vocab_n, grammar_n)
    else:
        item_type = {"v": "vocab", "g": "grammar", "b": None}[t]
        count = (vocab_n or 0) + (grammar_n or 0) if t == "b" else (vocab_n or grammar_n)
        await _run_review(chat_id, state, ctx, item_type, count)


async def _run_study(chat_id: int, state: SessionState, ctx: ContextTypes.DEFAULT_TYPE,
                     vocab_n: int, grammar_n: int) -> None:
    user_row = queries.get_user(chat_id)
    today = date.today().isoformat()
    cefr = user_row["cefr_level"]

    cached_story = queries.get_daily_story(chat_id, today)
    if cached_story:
        import json as _json
        vocab_ids = _json.loads(cached_story["vocab_ids"])[:vocab_n] if vocab_n else []
        grammar_id = cached_story["grammar_id"] if grammar_n else None
        vocab_items = queries.get_vocab_by_ids(vocab_ids)
        grammar_item = queries.get_grammar_by_id(grammar_id) if grammar_id else None
        if grammar_n and not grammar_item:
            grammar_item = await grammar_agent.get_daily_grammar(chat_id, cefr, today)
        story = {
            "story_text": cached_story["story_text"],
            "story_hook": cached_story["story_hook"],
            "word_callbacks": {},
        }
    else:
        vocab_items = await vocab_agent.get_daily_vocab(chat_id, cefr, today, n=vocab_n) if vocab_n else []
        grammar_item = await grammar_agent.get_daily_grammar(chat_id, cefr, today) if grammar_n else None

        if vocab_n and not vocab_items:
            await _send(chat_id, "Could not load today's lesson. Please try again shortly.", ctx)
            return
        if grammar_n and not grammar_item:
            await _send(chat_id, "Could not load today's grammar. Please try again shortly.", ctx)
            return

        items_for_story = vocab_items if vocab_items else []
        grammar_for_story = grammar_item if grammar_item else None
        if not items_for_story and not grammar_for_story:
            await _send(chat_id, "Nothing to study — try a different selection.", ctx)
            return
        story = await story_agent.generate_daily_story(chat_id, today, items_for_story, grammar_for_story)

    state.pending_vocab_ids = [v["item_id"] for v in vocab_items]
    state.session_total_vocab = len(state.pending_vocab_ids)
    state.pending_grammar_ids = [grammar_item["item_id"]] if grammar_item else []
    state.word_callbacks = story.get("word_callbacks", {})
    state.state = S.STORY_DISPLAY
    session_store.save(chat_id, state)

    await _send(chat_id,
        f"📖 <b>Today's Story</b>\n\n{_esc(story.get('story_text', ''))}\n\n<i>{_esc(story.get('story_hook', ''))}</i>",
        ctx, parse_mode="HTML",
        reply_markup=keyboards.continue_keyboard()
    )


async def _cmd_add(chat_id: int, state: SessionState, ctx: ContextTypes.DEFAULT_TYPE,
                   word: str | None = None) -> None:
    if word:
        state.state = S.USER_ADD_VOCAB_WORD
        session_store.save(chat_id, state)
        await _handle_add_word_input(chat_id, state, word, ctx)
    else:
        state.state = S.USER_ADD_VOCAB_WORD
        session_store.save(chat_id, state)
        await _send(chat_id, f"Which {LEARNING_LANGUAGE} word would you like to add to your deck?", ctx)


async def _cmd_stats(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    today = date.today().isoformat()
    s = queries.get_stats(chat_id, today)
    streak = queries.get_streak(chat_id)
    await _send(chat_id,
        f"<b>Your stats</b>\n"
        f"Level: {s['cefr_level']}\n"
        f"Cards in deck: {s['total_cards']}\n"
        f"Due today: {s['due_today']}\n"
        f"Total reviews: {s['total_reviews']}\n"
        f"🔥 Streak: {streak} day{'s' if streak != 1 else ''}",
        ctx, parse_mode="HTML"
    )


async def _cmd_report(chat_id: int, state: SessionState, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    state.state = S.REPORT_PERIOD
    session_store.save(chat_id, state)
    await _send(chat_id,
        "📊 <b>Report</b> — choose a period:\n\n"
        "1) Last week (7 days)\n"
        "2) Last month (30 days)\n"
        "3) Last 3 months (90 days)\n"
        "4) Custom — enter number of days",
        ctx, parse_mode="HTML")


async def _handle_report_period(chat_id: int, state: SessionState, text: str,
                                ctx: ContextTypes.DEFAULT_TYPE) -> None:
    mapping = {"1": 7, "2": 30, "3": 90}
    if text in mapping:
        state.report_period_days = mapping[text]
        state.state = S.REPORT_DETAIL
        session_store.save(chat_id, state)
        await _send(chat_id, "List all vocab and grammar? (yes / no)", ctx)
    elif text == "4":
        state.state = S.REPORT_CUSTOM_DAYS
        session_store.save(chat_id, state)
        await _send(chat_id, "How many days back? Enter a number.", ctx)
    else:
        await _send(chat_id, "Reply 1, 2, 3, or 4.", ctx)


async def _handle_report_custom_days(chat_id: int, state: SessionState, text: str,
                                     ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if text.isdigit() and int(text) > 0:
        state.report_period_days = int(text)
        state.state = S.REPORT_DETAIL
        session_store.save(chat_id, state)
        await _send(chat_id, "List all vocab and grammar? (yes / no)", ctx)
    else:
        await _send(chat_id, "Please enter a positive number.", ctx)


async def _handle_report_detail(chat_id: int, state: SessionState, text: str,
                                ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if text.lower() not in ("yes", "no", "y", "n"):
        await _send(chat_id, "Please reply yes or no.", ctx)
        return
    want_list = text.lower() in ("yes", "y")
    days = state.report_period_days or 7
    end = date.today()
    start = end - timedelta(days=days - 1)
    data = queries.get_report_data(chat_id, start.isoformat(), end.isoformat())

    start_str = start.strftime("%d %b").lstrip("0")
    end_str = end.strftime("%d %b").lstrip("0")
    lines = [
        f"<b>📊 {start_str} – {end_str} ({days} day{'s' if days != 1 else ''})</b>\n",
        f"📚 Learnt: {len(data['vocab_learnt'])} vocab, {len(data['grammar_learnt'])} grammar",
        f"🔁 Reviewed: {len(data['vocab_reviewed'])} vocab, {len(data['grammar_reviewed'])} grammar",
    ]
    if want_list:
        if data["vocab_learnt"]:
            lines.append(f"\nVocab learnt: {', '.join(data['vocab_learnt'])}")
        if data["grammar_learnt"]:
            lines.append(f"Grammar learnt: {', '.join(data['grammar_learnt'])}")
        if data["vocab_reviewed"]:
            lines.append(f"\nVocab reviewed: {', '.join(data['vocab_reviewed'])}")
        if data["grammar_reviewed"]:
            lines.append(f"Grammar reviewed: {', '.join(data['grammar_reviewed'])}")

    state.state = S.IDLE
    state.report_period_days = None
    session_store.save(chat_id, state)
    await _send(chat_id, "\n".join(lines), ctx, parse_mode="HTML")


# ── Placement ────────────────────────────────────────────────────────────────

async def _send_placement_question(chat_id: int, state: SessionState, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = assessor.get_question(state.placement_index)
    total = assessor.total_questions()
    text = (
        f"<b>Question {state.placement_index + 1}/{total}</b>\n\n"
        f"{_esc(q['question'])}\n\n"
        f"A) {_esc(q['options']['A'])}\n"
        f"B) {_esc(q['options']['B'])}\n"
        f"C) {_esc(q['options']['C'])}\n"
        f"D) {_esc(q['options']['D'])}"
    )
    await _send(chat_id, text, ctx, parse_mode="HTML", reply_markup=keyboards.mcq_keyboard())


async def _handle_placement_answer(chat_id: int, state: SessionState, answer: str,
                                   ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if answer.upper() not in ("A", "B", "C", "D"):
        return
    q = assessor.get_question(state.placement_index)
    correct = assessor.score_answer(q, answer)
    band = q["cefr_band"]
    state.placement_scores[band] = state.placement_scores.get(band, 0) + (1 if correct else 0)
    state.placement_index += 1

    if state.placement_index >= assessor.total_questions():
        await _send(chat_id, "Analysing your results...", ctx)
        result = await assessor.determine_level(state.placement_scores)
        level = result.get("level", "A1")
        justification = result.get("justification", "")
        queries.set_user_level(chat_id, level)
        state.state = S.PLACEMENT_COMPLETE
        session_store.save(chat_id, state)
        await _send(chat_id,
            f"<b>Your level: {_esc(level)}</b>\n\n{_esc(justification)}\n\nSend /study to start your first lesson!",
            ctx, parse_mode="HTML"
        )
    else:
        session_store.save(chat_id, state)
        await _send_placement_question(chat_id, state, ctx)


# ── Reviews ───────────────────────────────────────────────────────────────────

async def _start_lessons(chat_id: int, state: SessionState, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_next_vocab_lesson(chat_id, state, ctx)


async def _run_review(chat_id: int, state: SessionState, ctx: ContextTypes.DEFAULT_TYPE,
                      item_type: str | None, count: int) -> None:
    today = date.today().isoformat()
    due_cards = queries.get_due_cards(chat_id, today, item_type=item_type)
    due_cards = due_cards[:count] if count else due_cards
    state.pending_review_cards = [c["card_id"] for c in due_cards]

    if not state.pending_review_cards:
        await _send(chat_id, "No cards due for review today. Come back tomorrow!", ctx)
        return

    await _send(chat_id, f"<b>{len(state.pending_review_cards)} card(s)</b> due for review. Let's go!", ctx, parse_mode="HTML")
    await _send_next_review(chat_id, state, ctx)


async def _send_next_review(chat_id: int, state: SessionState, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    card_id = state.pending_review_cards[0]
    card = queries.get_card_by_id(card_id)
    card_data = await review_agent.present_review_card(card)
    state.current_card_id = card_id
    state.review_prompt = card_data.get("prompt", "")
    state.quiz_correct = card_data.get("correct", "A")
    state.quiz_explanation = card_data.get("explanation", "")
    state.state = S.REVIEW_PROMPT
    session_store.save(chat_id, state)

    options = card_data.get("options", {})
    options_text = "\n".join(f"{k}) {_esc(v)}" for k, v in options.items())
    remaining = len(state.pending_review_cards)
    await _send(chat_id,
        f"🔁 <b>Review</b> ({remaining} left)\n\n{_esc(card_data['prompt'])}\n\n{options_text}",
        ctx, parse_mode="HTML",
        reply_markup=keyboards.mcq_keyboard()
    )


async def _handle_review_answer(chat_id: int, state: SessionState, answer: str,
                                ctx: ContextTypes.DEFAULT_TYPE) -> None:
    correct = answer == state.quiz_correct
    icon = "✅" if correct else "❌"
    await _send(chat_id,
        f"{icon} {'Correct!' if correct else f'The answer was {_esc(state.quiz_correct)}.'}\n\n"
        f"{_esc(state.quiz_explanation or '')}\n\n"
        "How well did you remember? Rate 1–4:",
        ctx, parse_mode="HTML",
        reply_markup=keyboards.rating_keyboard()
    )
    state.state = S.REVIEW_ANSWER_SHOWN
    session_store.save(chat_id, state)


async def _handle_rating(chat_id: int, state: SessionState, rating: int,
                         ctx: ContextTypes.DEFAULT_TYPE) -> None:
    review_agent.process_rating(state.current_card_id, rating)
    state.pending_review_cards.pop(0)

    if state.pending_review_cards:
        await _send_next_review(chat_id, state, ctx)
    else:
        await _send(chat_id, "Reviews done! On to new lessons.", ctx)
        await _send_next_vocab_lesson(chat_id, state, ctx)


# ── Vocab lessons ─────────────────────────────────────────────────────────────

async def _send_next_vocab_lesson(chat_id: int, state: SessionState, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not state.pending_vocab_ids:
        await _send_grammar_lesson(chat_id, state, ctx)
        return

    item_id = state.pending_vocab_ids[0]
    item = queries.get_vocab_by_id(item_id)
    state.current_item_id = item_id
    state.current_item_type = "vocab"
    state.state = S.VOCAB_LESSON
    session_store.save(chat_id, state)

    callback = state.word_callbacks.get(item["word"], "")
    callback_line = f"\n\n<i>💡 Story moment: {_esc(callback)}</i>" if callback else ""

    text = (
        f"📚 <b>New word {state.session_total_vocab - len(state.pending_vocab_ids) + 1}/{state.session_total_vocab}</b>\n\n"
        f"<b>{_esc(item['word'])}</b> ({_esc(item['pinyin'])})\n"
        f"➜ {_esc(item['meaning'])}\n\n"
        f"📝 {_esc(item['example_sent'])}\n\n"
        f"🧠 Mnemonic: <i>{_esc(item['mnemonic'])}</i>"
        f"{callback_line}"
    )
    await _send(chat_id, text, ctx, parse_mode="HTML", reply_markup=keyboards.got_it_keyboard())


async def _send_vocab_quiz(chat_id: int, state: SessionState, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    item = queries.get_vocab_by_id(state.current_item_id)
    known = queries.get_known_vocab(chat_id, limit=15)
    quiz = await vocab_agent.generate_vocab_quiz(item, known)

    state.state = S.VOCAB_QUIZ
    state.quiz_correct = quiz.get("correct", "A")
    state.quiz_explanation = quiz.get("explanation", "")
    session_store.save(chat_id, state)

    opts = quiz.get("options", {})
    await _send(chat_id,
        f"🎯 <b>Quick quiz!</b>\n\n{_esc(quiz.get('question', ''))}\n\n"
        f"A) {_esc(opts.get('A',''))}\nB) {_esc(opts.get('B',''))}\nC) {_esc(opts.get('C',''))}\nD) {_esc(opts.get('D',''))}",
        ctx, parse_mode="HTML",
        reply_markup=keyboards.mcq_keyboard()
    )


async def _handle_vocab_quiz_answer(chat_id: int, state: SessionState, answer: str,
                                    ctx: ContextTypes.DEFAULT_TYPE) -> None:
    correct = state.quiz_correct or "A"
    explanation = state.quiz_explanation or ""
    icon = "✅" if answer == correct else "❌"
    await _send(chat_id, f"{icon} Correct answer: <b>{_esc(correct)}</b>\n<i>{_esc(explanation)}</i>",
                ctx, parse_mode="HTML")

    today = date.today().isoformat()
    queries.log_daily_item(chat_id, today, "vocab", state.current_item_id)
    queries.create_srs_card(chat_id, "vocab", state.current_item_id, today)

    state.pending_vocab_ids.pop(0)
    await _send_next_vocab_lesson(chat_id, state, ctx)


# ── Grammar lesson ────────────────────────────────────────────────────────────

async def _send_grammar_lesson(chat_id: int, state: SessionState, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not state.pending_grammar_ids:
        await _finish_session(chat_id, state, ctx)
        return

    item_id = state.pending_grammar_ids[0]
    item = queries.get_grammar_by_id(item_id)
    state.current_item_id = item_id
    state.current_item_type = "grammar"
    state.state = S.GRAMMAR_LESSON
    session_store.save(chat_id, state)

    await _send(chat_id,
        f"📖 <b>Today's Grammar</b>\n\n"
        f"<b>{_esc(item['pattern'])}</b>\n\n"
        f"{_esc(item['explanation'])}\n\n"
        f"📝 {_esc(item['example_sent'])}",
        ctx, parse_mode="HTML",
        reply_markup=keyboards.got_it_keyboard()
    )


async def _send_grammar_quiz(chat_id: int, state: SessionState, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    item = queries.get_grammar_by_id(state.current_item_id)
    known_vocab = queries.get_known_vocab(chat_id, limit=10)
    quiz = await grammar_agent.generate_grammar_quiz(item, known_vocab)

    state.state = S.GRAMMAR_QUIZ
    state.quiz_correct = quiz.get("correct", "A")
    state.quiz_explanation = quiz.get("explanation", "")
    session_store.save(chat_id, state)

    opts = quiz.get("options", {})
    await _send(chat_id,
        f"🎯 <b>Grammar quiz!</b>\n\n{_esc(quiz.get('question', ''))}\n\n"
        f"A) {_esc(opts.get('A',''))}\nB) {_esc(opts.get('B',''))}\nC) {_esc(opts.get('C',''))}\nD) {_esc(opts.get('D',''))}",
        ctx, parse_mode="HTML",
        reply_markup=keyboards.mcq_keyboard()
    )


async def _handle_grammar_quiz_answer(chat_id: int, state: SessionState, answer: str,
                                      ctx: ContextTypes.DEFAULT_TYPE) -> None:
    correct = state.quiz_correct or "A"
    explanation = state.quiz_explanation or ""
    icon = "✅" if answer == correct else "❌"
    await _send(chat_id, f"{icon} Correct answer: <b>{_esc(correct)}</b>\n<i>{_esc(explanation)}</i>",
                ctx, parse_mode="HTML")

    today = date.today().isoformat()
    queries.log_daily_item(chat_id, today, "grammar", state.current_item_id)
    queries.create_srs_card(chat_id, "grammar", state.current_item_id, today)

    state.pending_grammar_ids.pop(0)
    await _send_grammar_lesson(chat_id, state, ctx)


# ── User-add vocab flow ───────────────────────────────────────────────────────

async def _handle_add_word_input(chat_id: int, state: SessionState, word: str,
                                 ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await _send(chat_id, f"Looking up <b>{_esc(word)}</b>...", ctx, parse_mode="HTML")
    try:
        enriched = await vocab_agent.enrich_user_word(word)
    except Exception:
        state.state = S.IDLE
        session_store.save(chat_id, state)
        await _send(chat_id, "Sorry, couldn't look that up right now. Try again later.", ctx)
        return
    state.pending_add_word = word
    state.pending_add_enriched = enriched
    state.state = S.USER_ADD_VOCAB_CONFIRM
    session_store.save(chat_id, state)

    await _send(chat_id,
        f"<b>{_esc(enriched.get('word', word))}</b> ({_esc(enriched.get('pinyin', ''))})\n"
        f"➜ {_esc(enriched.get('meaning', ''))}\n\n"
        f"📝 {_esc(enriched.get('example_sent', ''))}\n\n"
        f"🧠 <i>{_esc(enriched.get('mnemonic', ''))}</i>\n\n"
        "Save this card?",
        ctx, parse_mode="HTML",
        reply_markup=keyboards.confirm_keyboard()
    )


async def _handle_add_confirm(chat_id: int, state: SessionState, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_row = queries.get_user(chat_id)
    cefr = user_row["cefr_level"] if user_row else "A1"
    e = state.pending_add_enriched or {}
    item_id = queries.insert_vocab(
        user_id=chat_id,
        word=e.get("word", state.pending_add_word or ""),
        pinyin=e.get("pinyin", ""),
        meaning=e.get("meaning", ""),
        example_sent=e.get("example_sent", ""),
        mnemonic=e.get("mnemonic", ""),
        cefr_level=cefr,
        source="user",
    )
    today = date.today().isoformat()
    queries.create_srs_card(chat_id, "vocab", item_id, today)

    state.state = S.IDLE
    state.pending_add_word = None
    state.pending_add_enriched = None
    session_store.save(chat_id, state)

    await _send(chat_id, f"Added <b>{_esc(e.get('word', ''))}</b> to your deck. It's due for review today!",
                ctx, parse_mode="HTML")


# ── Session end ───────────────────────────────────────────────────────────────

async def _finish_session(chat_id: int, state: SessionState, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    state.state = S.IDLE
    session_store.save(chat_id, state)
    await _send(chat_id, "That's a wrap for today! 🎉\n\nSee you tomorrow. Keep the story going!", ctx)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def _send(chat_id: int, text: str, ctx: ContextTypes.DEFAULT_TYPE,
                parse_mode: str = None, reply_markup=None) -> None:
    await ctx.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=parse_mode,
        reply_markup=reply_markup,
    )
