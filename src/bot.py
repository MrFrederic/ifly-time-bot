import logging
from telegram.ext import ConversationHandler, CommandHandler, CallbackQueryHandler, Application, MessageHandler, filters
from datetime import time
from .config import settings
from .handlers.buy import start_buy, date_selected, hours_selected, custom_date_handler, confirm_replace, SELECT_DATE, SELECT_HOURS, CONFIRM_REPLACE, custom_hours_handler, cancel_setup
# from .handlers.status import status_command
from .handlers.cancel import cancel_command
from .handlers.sticky import refresh_sticky_list
from .jobs import run_daily_matching_job, manual_matching_command
from time import sleep

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

def setup_handlers(application: Application):
    # Buy Conversation
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("buy", start_buy)],
        states={
            CONFIRM_REPLACE: [
                CallbackQueryHandler(cancel_setup, pattern="^cancel$"),
                CallbackQueryHandler(confirm_replace)
            ],
            SELECT_DATE: [
                CallbackQueryHandler(cancel_setup, pattern="^cancel$"),
                CallbackQueryHandler(date_selected),
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_date_handler)
            ],
            SELECT_HOURS: [
                CallbackQueryHandler(cancel_setup, pattern="^cancel$"),
                CallbackQueryHandler(hours_selected),
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_hours_handler)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)], # Allow exiting flow
        per_user=True,
        per_chat=False # Important for group chats so users have independent states
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start_command), group=1)
    # application.add_handler(CommandHandler("list", status_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("check_matches", manual_matching_command))
    
    # Sticky message listener (Group 1 to run in parallel)
    # We don't need to filter bot's own messages because they don't trigger handlers
    # Also we don't need to call refresh method from /buy and /cancel because those commands
    # will trigger this listener anyway + bot handles actual response first.
    application.add_handler(MessageHandler(filters.ALL & ~filters.UpdateType.EDITED, refresh_sticky_list), group=1)

async def start_command(update, context):
    text = (
        "👋 Привет! Я бот для помощи с распилом полетного времени\n"
        "Как только появятся подходящие запросы, чтобы распилить пакет, я сам соберу группу и пришлю уведомление!\n\n"
        "Используйте /buy чтобы создать новый запрос.\n"
        "Используйте /list чтобы увидеть активные запросы.\n"
        "Используйте /cancel чтобы удалить ваш запрос.\n\n"
        "Подсказка: если планируете покупать время, например, через месяц, вы можете создать запрос заранее и указать дату!"
    )
    await context.bot.send_message(chat_id=settings.ALLOWED_GROUP_ID, message_thread_id=settings.THREAD_ID, text=text, disable_notification=True, parse_mode='Markdown')

def setup_jobs(application: Application):
    job_queue = application.job_queue
    t = time(13, 00, tzinfo=settings.tz)
    job_queue.run_daily(run_daily_matching_job, t)
