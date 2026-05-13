import sqlite3
from datetime import date, timedelta
from agents.base import llm_call
from config import LEARNING_LANGUAGE
from core.sm2 import calculate_next_review, RATING_TO_QUALITY
from db import queries

_SYSTEM_PRESENT = f"""You are a {LEARNING_LANGUAGE} spaced-repetition reviewer.
Present the given item as a multiple-choice recall question in a FRESH context — never reuse the original example sentence.
Use a new scenario, sentence, or angle to test the same concept.

Formatting rules — follow exactly:
1. Instruction line: write the {LEARNING_LANGUAGE} instruction first, then the English translation in parentheses (e.g. "选择正确的词填空 (Choose the correct word to fill in the blank:)"). Always include both.
2. Sentence line: write the {LEARNING_LANGUAGE} sentence only — no English translation, no parentheses. If it is a fill-in-the-blank question, replace the missing word with exactly three underscores: ___.
3. Options: {LEARNING_LANGUAGE} only, no English translations.
4. Explanation: English only.

Return JSON: {{"prompt": "<English instruction>\\n<{LEARNING_LANGUAGE} sentence with ___ for blanks>", "options": {{"A": "", "B": "", "C": "", "D": ""}}, "correct": "<A|B|C|D>", "explanation": "<English explanation>"}}"""


async def present_review_card(card: sqlite3.Row) -> dict:
    if card["item_type"] == "vocab":
        item = queries.get_vocab_by_id(card["item_id"])
        context = f"Vocabulary: {item['word']} ({item['pinyin']}) — {item['meaning']}\nOriginal example: {item['example_sent']}"
    else:
        item = queries.get_grammar_by_id(card["item_id"])
        context = f"Grammar pattern: {item['pattern']}\nExplanation: {item['explanation']}\nOriginal example: {item['example_sent']}"

    return await llm_call(_SYSTEM_PRESENT, f"Item to review:\n{context}")


def process_rating(card_id: int, rating: int) -> None:
    card = queries.get_card_by_id(card_id)
    quality = RATING_TO_QUALITY[rating]
    new_interval, new_ef, new_reps = calculate_next_review(
        quality=quality,
        repetitions=card["repetitions"],
        ease_factor=card["ease_factor"],
        interval=card["interval"],
    )
    new_due = (date.today() + timedelta(days=new_interval)).isoformat()
    queries.log_review(
        card_id=card_id,
        quality=quality,
        interval_before=card["interval"],
        interval_after=new_interval,
        ease_before=card["ease_factor"],
        ease_after=new_ef,
    )
    queries.update_srs_card(card_id, new_interval, new_ef, new_reps, new_due)
