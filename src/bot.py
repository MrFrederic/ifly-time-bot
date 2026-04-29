import logging
from telegram import Update
from telegram.error import TelegramError, NetworkError, TimedOut, RetryAfter
from telegram.ext import CommandHandler, Application, MessageHandler, filters, ContextTypes
from datetime import time
from .config import settings
from .handlers.cancel import cancel_command
from .handlers.sticky import refresh_sticky_list
from .jobs import run_daily_matching_job, manual_matching_command

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler for the bot."""
    error = context.error
    if isinstance(error, NetworkError):
        logger.warning(f"NetworkError: {error}")
    elif isinstance(error, TimedOut):
        logger.warning(f"Request timed out: {error}")
    elif isinstance(error, RetryAfter):
        logger.warning(f"Rate limited. Retry after {error.retry_after}s")
    elif isinstance(error, TelegramError):
        logger.error(f"TelegramError: {error}", exc_info=context.error)
    else:
        logger.error(f"Unhandled exception: {error}", exc_info=context.error)


def setup_handlers(application: Application):
    application.add_handler(CommandHandler("start", start_command))
    # application.add_handler(CommandHandler("cancel", cancel_command))
    # application.add_handler(CommandHandler("check_matches", manual_matching_command))

    # Sticky message listener – runs on every message to keep dashboard at bottom
    application.add_handler(
        MessageHandler(filters.ALL & ~filters.UpdateType.EDITED, refresh_sticky_list),
        group=1,
    )

    application.add_error_handler(error_handler)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 Привет! Я бот для помощи с распилом полетного времени.\n"
        "Как только появятся подходящие запросы, чтобы распилить пакет, "
        "я сам соберу группу и пришлю уведомление!\n\n"
        "Используйте кнопку в закрепленном сообщении, чтобы создать или изменить или отменить запрос.\n"
    )
    await context.bot.send_message(
        chat_id=settings.ALLOWED_GROUP_ID,
        message_thread_id=settings.THREAD_ID,
        text=text,
        disable_notification=True,
        parse_mode='Markdown',
    )


def setup_jobs(application: Application):
    job_queue = application.job_queue
    t = time(13, 0, tzinfo=settings.tz)
    job_queue.run_daily(run_daily_matching_job, t)
