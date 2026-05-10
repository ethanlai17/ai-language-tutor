import sqlite3
from agents.base import llm_call
from db import queries

_SYSTEM_GENERATE = """You are a Mandarin Chinese vocabulary expert.
Generate a batch of vocabulary items for a {level} learner.
Return JSON: {{"items": [{{"word":"", "pinyin":"", "meaning":"", "example_sent":"", "mnemonic":""}}]}}
Produce exactly {n} items. Use simplified characters. Meanings in English.
Only include concrete content words: nouns, verbs, adjectives, and adverbs.
Do NOT include conjunctions, particles, grammar patterns, or sentence structures (e.g. 虽然, 因为, 把, 是…的)."""

_SYSTEM_ENRICH = """You are a Mandarin Chinese vocabulary expert.
Given a Chinese word, return: pinyin, English meaning, a natural example sentence in Chinese (with English translation), and a vivid mnemonic.
Return JSON: {{"word":"", "pinyin":"", "meaning":"", "example_sent":"", "mnemonic":""}}"""

_SYSTEM_QUIZ = """You are a creative Mandarin Chinese vocabulary quiz writer.
Generate a multiple-choice quiz question testing recall of the given word.
Use the known_words as plausible distractors where relevant.
Return JSON: {{"question":"", "options":{{"A":"","B":"","C":"","D":""}},"correct":"<A|B|C|D>","explanation":""}}"""

VOCAB_POOL_MIN = 10
VOCAB_BATCH_SIZE = 20


async def ensure_vocab_pool(user_id: int, cefr_level: str, today: str) -> None:
    count = queries.get_vocab_pool_count(user_id, cefr_level, today)
    if count < VOCAB_POOL_MIN:
        result = await llm_call(
            _SYSTEM_GENERATE.format(level=cefr_level, n=VOCAB_BATCH_SIZE),
            f"Generate {VOCAB_BATCH_SIZE} {cefr_level} level Mandarin vocabulary items."
        )
        for item in result.get("items", []):
            queries.insert_vocab(
                user_id=user_id,
                word=item.get("word", ""),
                pinyin=item.get("pinyin", ""),
                meaning=item.get("meaning", ""),
                example_sent=item.get("example_sent", ""),
                mnemonic=item.get("mnemonic", ""),
                cefr_level=cefr_level,
                source="system",
            )


async def get_daily_vocab(user_id: int, cefr_level: str, today: str, n: int = 5) -> list[sqlite3.Row]:
    await ensure_vocab_pool(user_id, cefr_level, today)
    return queries.select_daily_vocab(user_id, cefr_level, today, n=n)


async def enrich_user_word(word: str) -> dict:
    return await llm_call(_SYSTEM_ENRICH, f"Word: {word}")


async def generate_vocab_quiz(item: sqlite3.Row, known_items: list[sqlite3.Row]) -> dict:
    known = [{"word": r["word"], "meaning": r["meaning"]} for r in known_items]
    return await llm_call(
        _SYSTEM_QUIZ,
        f"Target word: {item['word']} ({item['pinyin']}) — {item['meaning']}\n"
        f"Example: {item['example_sent']}\n"
        f"Known words for distractors: {known}"
    )
