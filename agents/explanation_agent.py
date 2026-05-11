from agents.base import llm_call_text


async def explain(user_question: str, bot_message: str, language: str) -> str:
    system = (
        f"You are a {language} language tutor. "
        f"The student is studying and has a question about the following bot message:\n\n"
        f"{bot_message}\n\n"
        "Answer their question concisely in English. Be direct and helpful."
    )
    return await llm_call_text(system, user_question)
