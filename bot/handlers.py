import logging
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

logger = logging.getLogger(__name__)


async def _dispatch(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await orchestrator.handle(update, ctx)


async def _error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception", exc_info=ctx.error)
    if isinstance(update, Update) and update.effective_chat:
        await ctx.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Something went wrong. Please try again.",
        )


def register(app: Application) -> None:
    app.add_handler(CommandHandler("start", _dispatch))
    app.add_handler(CommandHandler("study", _dispatch))
    app.add_handler(CommandHandler("review", _dispatch))
    app.add_handler(CommandHandler("add", _dispatch))
    app.add_handler(CommandHandler("stats", _dispatch))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _dispatch))
    app.add_handler(CallbackQueryHandler(_dispatch))
    app.add_error_handler(_error_handler)
