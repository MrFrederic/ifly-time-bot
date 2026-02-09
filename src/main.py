import logging
from telegram.ext import ApplicationBuilder
from .config import settings
from .database import init_db
from .bot import setup_handlers, setup_jobs

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=settings.LOG_LEVEL
)
logger = logging.getLogger(__name__)

# Configure python-telegram-bot library loggers to use the same log level
logging.getLogger("telegram").setLevel(settings.LOG_LEVEL)
logging.getLogger("telegram.ext").setLevel(settings.LOG_LEVEL)
logging.getLogger("httpx").setLevel(settings.LOG_LEVEL)
logging.getLogger("httpcore").setLevel(settings.LOG_LEVEL)
logging.getLogger("apscheduler").setLevel(settings.LOG_LEVEL)

def main():
    # Initialize Database
    logger.info("Initializing Database...")
    try:
        init_db()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    # Validate Telegram token
    if not settings.TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN is not set. Cannot start bot.")
        raise ValueError("TELEGRAM_TOKEN must be set")

    # Build Application
    logger.info("Building Bot Application...")
    try:
        application = ApplicationBuilder().token(settings.TELEGRAM_TOKEN).build()
    except Exception as e:
        logger.error(f"Failed to build Telegram application: {e}")
        raise

    # Disabling concurrency to prevent issues with ConversationHandler
    # application.concurrent_updates = 0

    # Setup Handlers
    setup_handlers(application)
    setup_jobs(application)

    # Run
    if settings.CONNECTION_MODE.lower() == "webhook":
        if not settings.WEBHOOK_URL:
            logger.error("WEBHOOK_URL is not set but CONNECTION_MODE is 'webhook'. Cannot start bot.")
            raise ValueError("WEBHOOK_URL must be set when using webhook mode")
        logger.info(f"Starting Webhook on port {settings.PORT}...")
        try:
            application.run_webhook(
                listen="0.0.0.0",
                port=settings.PORT,
                url_path=settings.TELEGRAM_TOKEN,
                webhook_url=f"{settings.WEBHOOK_URL}/{settings.TELEGRAM_TOKEN}"
            )
        except Exception as e:
            logger.error(f"Failed to start webhook: {e}")
            raise
    elif settings.CONNECTION_MODE.lower() == "polling":
        logger.info("Starting Polling...")
        try:
            application.run_polling()
        except Exception as e:
            logger.error(f"Failed to start polling: {e}")
            raise
    else:
        logger.error(f"Invalid CONNECTION_MODE: '{settings.CONNECTION_MODE}'. Must be 'polling' or 'webhook'.")
        raise ValueError(f"Invalid CONNECTION_MODE: {settings.CONNECTION_MODE}")

if __name__ == '__main__':
    main()
