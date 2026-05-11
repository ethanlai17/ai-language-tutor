from datetime import date
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import Application
from agents.base import llm_call
from config import TELEGRAM_CHAT_ID, NOTIFICATION_HOUR, NOTIFICATION_MINUTE, NOTIFICATION_TIMEZONE, LEARNING_LANGUAGE
from db.queries import has_activity_today, get_streak

_SYSTEM_NUDGE = f"""You are a chaotic, unhinged language tutor generating a daily reminder to study {LEARNING_LANGUAGE}.
Generate exactly ONE reminder. Rules:
- Under 7 words total (not counting emoji)
- Wildly funny — rotate freely between: absurd threats, existential dread, fake urgency, cursed wisdom, dramatic flattery, nonsense prophecy
- One emoji allowed, optional
- Never generic ("study now", "don't forget")
Return JSON: {"reminder": "<text>"}"""


def setup(app: Application) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    async def send_daily_nudge() -> None:
        today = date.today().isoformat()
        if has_activity_today(TELEGRAM_CHAT_ID, today):
            return
        streak = get_streak(TELEGRAM_CHAT_ID)
        streak_context = (
            f" The user has a {streak}-day streak. Mention the streak count to motivate them to protect it."
            if streak >= 3 else ""
        )
        result = await llm_call(_SYSTEM_NUDGE, f"Generate today's reminder.{streak_context}")
        text = result.get("reminder", f"Your {LEARNING_LANGUAGE} awaits. Don't be a coward.")
        await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)

    scheduler.add_job(
        send_daily_nudge,
        CronTrigger(hour=NOTIFICATION_HOUR, minute=NOTIFICATION_MINUTE, timezone=NOTIFICATION_TIMEZONE),
    )
    return scheduler
