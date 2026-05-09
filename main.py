from telegram.ext import ApplicationBuilder
from config import TELEGRAM_BOT_TOKEN, validate
from db.schema import run_migrations
from bot.handlers import register
from bot.notifications import setup


def main() -> None:
    validate()
    run_migrations()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    register(app)

    scheduler = setup(app)

    async def on_startup(_application) -> None:
        scheduler.start()

    app.post_init = on_startup

    print("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
