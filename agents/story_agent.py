from agents.base import llm_call
from db import queries

_SYSTEM = """You are a wildly creative serialised storyteller and Mandarin Chinese tutor.
Each day you continue an ongoing story — you MUST pick up exactly where the previous day's
hook left off, even if the transition is jarring or absurd (awkward continuations are a
FEATURE, not a bug — they make words unforgettable).
Weave ALL provided vocabulary words and the grammar pattern naturally into the story.
Bold each target word on first use using **word** markdown syntax.
Keep the tone playful, surprising, and slightly unhinged.
End with a punchy 1-2 sentence cliffhanger hook for tomorrow.
Also produce a one-line "callback" per vocabulary word capturing the memorable story moment.

Return ONLY valid JSON in this exact shape:
{
  "story_text": "<full story in English with **bolded** Chinese words inline>",
  "story_hook": "<1-2 sentence cliffhanger>",
  "word_callbacks": {"<chinese_word>": "<one-line story moment>"}
}"""


async def generate_daily_story(
    user_id: int,
    today: str,
    vocab_items: list,
    grammar_item,
) -> dict:
    cached = queries.get_daily_story(user_id, today)
    if cached:
        return {"story_text": cached["story_text"], "story_hook": cached["story_hook"], "word_callbacks": {}}

    previous_hook = queries.get_last_story_hook(user_id)

    vocab_list = [
        f"{v['word']} ({v['pinyin']}) — {v['meaning']}"
        for v in vocab_items
    ]

    prompt_parts = []
    if previous_hook:
        prompt_parts.append(f"PREVIOUS STORY HOOK (continue from here): {previous_hook}")
    else:
        prompt_parts.append("This is DAY 1 — start a brand-new story. Make it memorable and set up a rich world.")

    if vocab_list:
        prompt_parts.append(f"\nToday's vocabulary to use:\n" + "\n".join(f"- {v}" for v in vocab_list))
    if grammar_item:
        prompt_parts.append(f"\nToday's grammar pattern to demonstrate: {grammar_item['pattern']}")
    prompt_parts.append("\nWrite the next chapter of the story now.")

    result = await llm_call(_SYSTEM, "\n".join(prompt_parts))

    vocab_ids = [v["item_id"] for v in vocab_items]
    queries.save_daily_story(
        user_id=user_id,
        log_date=today,
        story_text=result.get("story_text", ""),
        story_hook=result.get("story_hook", ""),
        vocab_ids=vocab_ids,
        grammar_id=grammar_item["item_id"] if grammar_item else 0,
    )

    return result
