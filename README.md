# AI Language Tutor

A personal Mandarin Chinese tutor that runs as a Telegram bot. It learns your level, teaches you new words and grammar every day through a continuing serialised story, and uses spaced repetition (like Anki) to make sure you actually remember what you've learned.

## What it does

**First run** — a 30-question multiple-choice placement test assigns you a CEFR level (A1–C2).

**Every day** — send `/study` to get:
- A continuing story that weaves together all 5 new vocabulary words and 1 new grammar point. The story picks up exactly where yesterday's cliffhanger left off (awkward transitions are intentional — they make words stick).
- Any vocabulary or grammar cards due for review, scheduled by the SM-2 spaced repetition algorithm.
- A quiz on each new word and grammar point before moving on.

**Anytime** — send `/add 某个词` to add your own word. The bot enriches it with pinyin, meaning, example sentence, and a mnemonic, then adds it to your review deck immediately.

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

The other values have sensible defaults. Change `NOTIFICATION_TIMEZONE` if you're not in Asia/Shanghai.

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
| `/study` | Start today's lesson — story, reviews, new vocab, new grammar |
| `/add <word>` | Add a Mandarin word to your personal deck |
| `/stats` | See your current level, deck size, cards due today, and total reviews |

## Cost

At steady state (~40 LLM calls/day), DeepSeek-V3 costs roughly **$0.02–0.04 per day**. Telegram is free. SQLite is free.

## Running tests

```bash
python -m pytest tests/ -v
```

No API keys needed — all external calls are mocked.
