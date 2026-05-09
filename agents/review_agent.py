import sqlite3
from datetime import date, timedelta
from agents.base import llm_call
from core.sm2 import calculate_next_review, RATING_TO_QUALITY
from db import queries

_SYSTEM_PRESENT = """You are a Mandarin Chinese spaced-repetition reviewer.
Present the given item as a recall prompt in a FRESH context — never reuse the original example sentence.
Use a new scenario, sentence, or angle to test the same concept.
Return JSON: {{"prompt": "<question to show the student>", "answer": "<correct answer with explanation>"}}"""

_SYSTEM_EVALUATE = """You are a strict-but-fair Mandarin Chinese answer evaluator.
The student answered a recall question. Evaluate if their answer is correct.
Be strict about meaning but lenient about minor pinyin tone marks and romanisation variants.
Return JSON: {{"correct": <true|false>, "feedback": "<1-2 sentence feedback>"}}"""


async def present_review_card(card: sqlite3.Row) -> dict:
    if card["item_type"] == "vocab":
        item = queries.get_vocab_by_id(card["item_id"])
        context = f"Vocabulary: {item['word']} ({item['pinyin']}) — {item['meaning']}\nOriginal example: {item['example_sent']}"
    else:
        item = queries.get_grammar_by_id(card["item_id"])
        context = f"Grammar pattern: {item['pattern']}\nExplanation: {item['explanation']}\nOriginal example: {item['example_sent']}"

    return await llm_call(_SYSTEM_PRESENT, f"Item to review:\n{context}")


async def evaluate_answer(question: str, correct_answer: str, user_answer: str) -> dict:
    return await llm_call(
        _SYSTEM_EVALUATE,
        f"Question: {question}\nCorrect answer: {correct_answer}\nStudent answer: {user_answer}"
    )


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
