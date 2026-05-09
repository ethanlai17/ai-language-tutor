from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from agents import orchestrator


async def _dispatch(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await orchestrator.handle(update, ctx)


def register(app: Application) -> None:
    app.add_handler(CommandHandler("start", _dispatch))
    app.add_handler(CommandHandler("study", _dispatch))
    app.add_handler(CommandHandler("add", _dispatch))
    app.add_handler(CommandHandler("stats", _dispatch))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _dispatch))
    app.add_handler(CallbackQueryHandler(_dispatch))
