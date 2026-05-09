from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import Application
from config import TELEGRAM_CHAT_ID, NOTIFICATION_HOUR, NOTIFICATION_MINUTE, NOTIFICATION_TIMEZONE


def setup(app: Application) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    async def send_daily_nudge() -> None:
        await app.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="Good morning! Your Mandarin lesson is ready. Send /study to continue the story 📖",
        )

    scheduler.add_job(
        send_daily_nudge,
        CronTrigger(
            hour=NOTIFICATION_HOUR,
            minute=NOTIFICATION_MINUTE,
            timezone=NOTIFICATION_TIMEZONE,
        ),
    )
    return scheduler
