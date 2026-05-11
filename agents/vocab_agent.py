import sqlite3
from agents.base import llm_call
from config import LEARNING_LANGUAGE
from db import queries

_SYSTEM_GENERATE = """You are a {language} vocabulary expert.
Generate a batch of vocabulary items for a {{level}} learner.
Return JSON: {{"items": [{{"word":"", "pinyin":"", "meaning":"", "example_sent":"", "mnemonic":""}}]}}
Produce exactly {{n}} items. Meanings in English.
Only include concrete content words: nouns, verbs, adjectives, and adverbs.
Do NOT include conjunctions, particles, grammar patterns, or sentence structures."""

_SYSTEM_ENRICH = f"""You are a {LEARNING_LANGUAGE} vocabulary expert.
Given a word in the target language, return: romanisation/pronunciation, English meaning, a natural example sentence (with English translation), and a vivid mnemonic.
Return JSON: {{"word":"", "pinyin":"", "meaning":"", "example_sent":"", "mnemonic":""}}"""

_SYSTEM_QUIZ = f"""You are a creative {LEARNING_LANGUAGE} vocabulary quiz writer.
Generate a multiple-choice quiz question testing recall of the given word.
Use the known_words as plausible distractors where relevant.
Rules for JSON fields:
- "question": write the instruction in the target language with its English translation in parentheses on the same line, then the target language sentence/prompt on the next line with its English translation in parentheses on the same line
- "options": target language only, no translations
- "explanation": write the explanation in the target language followed immediately by its English translation in parentheses
Return JSON: {{"question":"<target language instruction> (<English>) \\n<target language sentence> (<English>)", "options":{{"A":"","B":"","C":"","D":""}},"correct":"<A|B|C|D>","explanation":"<target language> (<English>)"}}"""

VOCAB_POOL_MIN = 10
VOCAB_BATCH_SIZE = 20


async def ensure_vocab_pool(user_id: int, cefr_level: str, today: str) -> None:
    count = queries.get_vocab_pool_count(user_id, cefr_level, today)
    if count < VOCAB_POOL_MIN:
        result = await llm_call(
            _SYSTEM_GENERATE.format(language=LEARNING_LANGUAGE, level=cefr_level, n=VOCAB_BATCH_SIZE),
            f"Generate {VOCAB_BATCH_SIZE} {cefr_level} level {LEARNING_LANGUAGE} vocabulary items."
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
