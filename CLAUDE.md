# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests
python -m pytest tests/ -v

# Run a single test
python -m pytest tests/test_orchestrator_flow.py::test_grammar_lesson_and_quiz -v

# Run the bot
python main.py

# Install dependencies
pip install -r requirements.txt
```

Tests require no real API keys — all LLM and Telegram calls are mocked.

## Architecture

Multi-agent Telegram bot for language learning (configurable via `LEARNING_LANGUAGE` env var, defaults to Mandarin Chinese). Entry point: `main.py` → registers handlers → starts `APScheduler` via `post_init` hook (requires a running event loop) → `run_polling()`.

### Request flow

Every Telegram message/callback routes through `agents/orchestrator.py::handle()`, which:
1. Deduplicates `CallbackQuery` by ID (module-level `_seen_callbacks` set — cleared in tests via fixture)
2. Upserts the user row
3. Reads `SessionState` from `core/session_store.py` (in-memory dict, write-through to `sessions` DB table)
4. Dispatches to the appropriate private function based on `ConversationState` enum

### State machine

`core/state_machine.py` defines `ConversationState` (enum) and `SessionState` (dataclass). All mid-session data — current card, quiz answer, review prompt, word callbacks — lives in `SessionState` and is serialised to `sessions.context_json` on every transition so the bot survives restarts. Use `state.quiz_correct` / `state.review_answer` etc. (not ad-hoc attributes).

### Daily session flow

```
/study → check daily_stories cache
       → if cached: reload vocab/grammar from stored IDs (ensures story ↔ lesson consistency)
       → if new: pool seeding → StoryAgent (one LLM call, saved to daily_stories)
       → STORY_DISPLAY → "Continue" button
       → 5 × VOCAB_LESSON → VOCAB_QUIZ
       → GRAMMAR_LESSON → GRAMMAR_QUIZ → IDLE

/review → fetch due cards (srs_cards WHERE due_date <= today)
        → MCQ-style REVIEW_PROMPT → REVIEW_ANSWER_SHOWN (rate 1–4) → repeat → IDLE

/report → REPORT_PERIOD (choose 1–4)
        → [if 4] REPORT_CUSTOM_DAYS (enter number)
        → REPORT_DETAIL (yes/no for word listing)
        → summary counts (+ comma-separated word lists if yes) → IDLE
```

**Important:** vocab/grammar IDs are stored in `daily_stories.vocab_ids` (JSON) and `daily_stories.grammar_id`. On repeat `/study` calls within the same day, the orchestrator reads these IDs and calls `queries.get_vocab_by_ids()` to load the exact same items the story was written around — preventing a mismatch between cached story and newly selected words.

### Agents

Each agent in `agents/` makes LLM calls via `agents/base.py::llm_call()` (async, `response_format=json_object`, 3 retries). All agents use the DeepSeek API via the OpenAI-compatible SDK.

| Agent | Responsibility |
|---|---|
| `assessor.py` | 30-question placement test from static JSON; one LLM call at the end to assign CEFR level |
| `vocab_agent.py` | Pool seeding (batch of 20), daily selection, user-word enrichment, quiz generation |
| `grammar_agent.py` | Pool seeding (batch of 10), daily selection, quiz generation |
| `story_agent.py` | Serialised story using today's 5 vocab + 1 grammar; continues from `story_hook` stored in `daily_stories` table |
| `review_agent.py` | SM-2 scheduling, MCQ-style card presentation (no free-text evaluation) |
| `orchestrator.py` | Pure routing, no LLM calls |

### Spaced repetition

`core/sm2.py::calculate_next_review(quality, repetitions, ease_factor, interval)` — pure function, no I/O. `RATING_TO_QUALITY` maps user-facing 1–4 labels to SM-2 quality scores. `review_agent.process_rating()` calls SM-2, writes to `srs_cards`, and logs to `review_log`.

### Database

SQLite via stdlib `sqlite3`. `db/schema.py::run_migrations()` is idempotent (safe to call on every startup). `db/queries.py` is the only layer that touches SQL — no raw SQL in agents or orchestrator.

Key tables: `users`, `vocab_items`, `grammar_items`, `srs_cards` (SM-2 state), `review_log` (immutable history), `sessions` (conversation state), `daily_log` (delivery deduplication), `daily_stories` (story continuity).

Key query functions: `get_report_data(user_id, start_date, end_date)` — returns vocab/grammar learnt (from `daily_log`) and reviewed (from `review_log`) in a date range. `get_streak(user_id)` — counts consecutive activity days walking back from today via a UNION of `daily_log` and `review_log` dates.

### Streak system

`db/queries.py::get_streak(user_id)` computes consecutive active days (any `/study` or `/review` activity). Shown in `/stats`. The 10pm scheduler in `bot/notifications.py` calls `get_streak()` before sending the reminder; if the streak is ≥ 3 days, the count is passed to the LLM prompt so the reminder mentions it.

### 10pm reminder

`bot/notifications.py` fires daily at 22:00 Europe/London (configurable via `NOTIFICATION_HOUR` / `NOTIFICATION_TIMEZONE` env vars). Skipped entirely if the user already has any activity today (`has_activity_today()`). Otherwise an LLM-generated funny message (<7 words) is sent, optionally mentioning the streak if ≥ 3 days.

### Configuration

All settings loaded from `.env` via `config.py`. Call `config.validate()` at startup (done in `main.py`) to fail fast on missing required keys. Copy `.env.example` to `.env` to get started.
