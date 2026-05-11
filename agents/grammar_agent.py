import sqlite3
from agents.base import llm_call
from config import LEARNING_LANGUAGE
from db import queries

_SYSTEM_GENERATE = """You are a {language} grammar expert.
Generate grammar points for a {{level}} learner.
Return JSON: {{"items": [{{"pattern":"", "explanation":"", "example_sent":""}}]}}
Produce exactly {{n}} items. Each pattern should be a named construction.
Explanation should be 2-3 sentences. Include a correct example and a contrast with a common learner mistake in example_sent."""

_SYSTEM_QUIZ = f"""You are a {LEARNING_LANGUAGE} grammar quiz writer.
Generate a quiz question testing the student's understanding of the given grammar pattern.
Use some of the known vocabulary words in the question to reinforce vocabulary too.
Rules for JSON fields:
- "question": write the instruction in the target language with its English translation in parentheses on the same line, then the target language sentence/prompt on the next line with its English translation in parentheses on the same line
- "options": target language only, no translations
- "explanation": write the explanation in the target language followed immediately by its English translation in parentheses
Return JSON: {{"question":"<target language instruction> (<English>) \\n<target language sentence> (<English>)", "options":{{"A":"","B":"","C":"","D":""}},"correct":"<A|B|C|D>","explanation":"<target language> (<English>)"}}"""

GRAMMAR_POOL_MIN = 5
GRAMMAR_BATCH_SIZE = 10


async def ensure_grammar_pool(user_id: int, cefr_level: str, today: str) -> None:
    count = queries.get_grammar_pool_count(user_id, cefr_level)
    if count < GRAMMAR_POOL_MIN:
        result = await llm_call(
            _SYSTEM_GENERATE.format(language=LEARNING_LANGUAGE, level=cefr_level, n=GRAMMAR_BATCH_SIZE),
            f"Generate {GRAMMAR_BATCH_SIZE} {cefr_level} level {LEARNING_LANGUAGE} grammar points."
        )
        for item in result.get("items", []):
            queries.insert_grammar(
                user_id=user_id,
                pattern=item.get("pattern", ""),
                explanation=item.get("explanation", ""),
                example_sent=item.get("example_sent", ""),
                cefr_level=cefr_level,
                source="system",
            )


async def get_daily_grammar(user_id: int, cefr_level: str, today: str) -> sqlite3.Row | None:
    await ensure_grammar_pool(user_id, cefr_level, today)
    return queries.select_daily_grammar(user_id, cefr_level, today)


async def generate_grammar_quiz(item: sqlite3.Row, known_vocab: list[sqlite3.Row]) -> dict:
    vocab_list = [{"word": r["word"], "meaning": r["meaning"]} for r in known_vocab]
    return await llm_call(
        _SYSTEM_QUIZ,
        f"Grammar pattern: {item['pattern']}\n"
        f"Explanation: {item['explanation']}\n"
        f"Example: {item['example_sent']}\n"
        f"Known vocabulary to incorporate: {vocab_list}"
    )
