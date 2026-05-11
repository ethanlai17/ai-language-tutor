import json
from pathlib import Path
from agents.base import llm_call
from config import LEARNING_LANGUAGE

_QUESTIONS: list[dict] = json.loads(
    (Path(__file__).parent.parent / "data" / "placement_questions.json").read_text()
)

SYSTEM_PROMPT = f"""You are a {LEARNING_LANGUAGE} proficiency assessor.
You will receive a summary of a 30-question placement test: the number of correct answers
per CEFR band (A1, A2, B1, B2, C1, C2). Return a JSON object:
{{"level": "<A1|A2|B1|B2|C1|C2>", "justification": "<friendly 2-3 sentence explanation>"}}
Base the level on the highest band where the student scored >= 60%.
If all bands are below 60%, return A1. If all bands are 100%, return C2."""


def get_question(index: int) -> dict:
    return _QUESTIONS[index]


def total_questions() -> int:
    return len(_QUESTIONS)


def score_answer(question: dict, answer: str) -> bool:
    return answer.upper() == question["correct"]


async def determine_level(scores: dict) -> dict:
    score_summary = ", ".join(f"{band}: {count}/5" for band, count in sorted(scores.items()))
    return await llm_call(SYSTEM_PROMPT, f"Scores per band: {score_summary}")
