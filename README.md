# AI Language Tutor

A personal language tutor that runs as a Telegram bot. It learns your level, teaches you new words and grammar every day through a continuing serialised story, and uses spaced repetition (like Anki) to make sure you actually remember what you've learned. A streak system, activity reports, and a nightly reminder keep you consistent. Works with any language — set `LEARNING_LANGUAGE` in your `.env` to get started.

## What it does

**First run** — a 30-question multiple-choice placement test assigns you a CEFR level (A1–C2).

**Every day** — two commands keep you progressing:

- `/study` — a continuing story that weaves together 5 new vocabulary words and 1 new grammar point, picking up exactly where yesterday's cliffhanger left off (awkward transitions are intentional — they make words stick). Followed by a quiz on each new word and grammar point.
- `/review` — work through any cards due today using multiple-choice questions, scheduled by the SM-2 spaced repetition algorithm. Rate each answer 1–4 to set the next review interval.

**Anytime** — send `/add <word>` to add your own word. The bot enriches it with pronunciation, meaning, example sentence, and a mnemonic, then adds it to your review deck immediately.

**Streak tracking** — any day you complete a `/study` or `/review` session counts toward your streak. The current streak is shown in `/stats`. Miss a day and it resets to zero — just like Duolingo.

**Reports** — `/report` walks you through choosing a time period (last week, month, 3 months, or a custom number of days) and shows a breakdown of how many words and grammar points you studied and reviewed. Optionally lists every item by name.

**Daily reminder** — at 10pm (configurable) the bot sends a short, LLM-generated funny nudge if you haven't been active that day. Once your streak reaches 3+ days the reminder mentions it to raise the stakes. No message is sent on days you've already studied or reviewed.

## Setup

### 1. Get the required API keys

| Key | Where to get it |
|---|---|
| Telegram bot token | Message [@BotFather](https://t.me/botfather) on Telegram → `/newbot` |
| Your Telegram chat ID | Message [@userinfobot](https://t.me/userinfobot) |
| DeepSeek API key | [platform.deepseek.com](https://platform.deepseek.com) — free trial available |

### 2. Install dependencies

Python 3.11+ required.

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in your keys:

```
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
DEEPSEEK_API_KEY=your_key_here
```

The other values have sensible defaults. `NOTIFICATION_HOUR` defaults to `22` and `NOTIFICATION_TIMEZONE` defaults to `Europe/London`.

### 4. Run

```bash
python main.py
```

The bot will create `tutor.db` on first run (SQLite, no setup needed) and start polling. Open Telegram and send `/start`.

To keep it running persistently, use a tool like `screen`, `tmux`, or deploy it to any cheap VPS.

## Commands

| Command | What it does |
|---|---|
| `/start` | Run the placement test (first time only), or jump straight to `/study` |
| `/study` | Today's story + quiz on each new word and grammar point |
| `/review` | Multiple-choice review of all SRS cards due today |
| `/add <word>` | Add a word in your target language to your personal deck |
| `/stats` | Your level, deck size, cards due, total reviews, and current streak |
| `/report` | Activity report for a chosen period — counts of vocab/grammar learnt and reviewed, with optional word listing |

## Cost

At steady state (~40 LLM calls/day), DeepSeek-V3 costs roughly **$0.02–0.04 per day**. Telegram is free. SQLite is free.

## Running tests

```bash
python -m pytest tests/ -v
```

No API keys needed — all external calls are mocked.
