import asyncio
import logging
import uvicorn
from telegram.ext import ApplicationBuilder
from .config import settings
from .database import init_db
from .bot import setup_handlers, setup_jobs
from .webapp.app import create_app

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=settings.LOG_LEVEL
)
logger = logging.getLogger(__name__)

# Configure library loggers
logging.getLogger("telegram").setLevel(settings.LOG_LEVEL)
logging.getLogger("telegram.ext").setLevel(settings.LOG_LEVEL)
logging.getLogger("httpx").setLevel(settings.LOG_LEVEL)
logging.getLogger("httpcore").setLevel(settings.LOG_LEVEL)
logging.getLogger("apscheduler").setLevel(settings.LOG_LEVEL)


def _masked_token(token: str) -> str:
    if not token:
        return "<empty>"
    if len(token) <= 8:
        return "***"
    return f"{token[:5]}...{token[-3:]}"


async def main():
    logger.info("=== ifly-time-bot startup begin ===")
    logger.info(
        "Startup config: mode=%s, log_level=%s, timezone=%s, webapp_port=%s, webhook_port=%s",
        settings.CONNECTION_MODE,
        settings.LOG_LEVEL,
        settings.TIMEZONE,
        settings.WEBAPP_PORT,
        settings.PORT,
    )

    if settings.CONNECTION_MODE.lower() == "polling" and settings.PORT != settings.WEBAPP_PORT:
        logger.warning(
            "Polling mode uses WEBAPP_PORT=%s for FastAPI. PORT=%s only affects Telegram webhook mode.",
            settings.WEBAPP_PORT,
            settings.PORT,
        )

    # Initialize Database
    logger.info("Initializing Database...")
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    # Validate Telegram token
    if not settings.TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN is not set. Cannot start bot.")
        raise ValueError("TELEGRAM_TOKEN must be set")

    # Build bot application
    logger.info("Building Bot Application (token=%s)...", _masked_token(settings.TELEGRAM_TOKEN))
    try:
        application = ApplicationBuilder().token(settings.TELEGRAM_TOKEN).build()
        logger.info("Telegram Application built successfully")
    except Exception as e:
        logger.error(f"Failed to build Telegram application: {e}")
        raise

    setup_handlers(application)
    setup_jobs(application)

    # Create FastAPI webapp (shares the bot instance)
    webapp = create_app(application)
    logger.info("FastAPI app created and routes registered")

    # Start bot
    logger.info("Initializing Telegram application...")
    await application.initialize()
    logger.info("Starting Telegram application...")
    await application.start()
    logger.info("Telegram application started")

    if settings.CONNECTION_MODE.lower() == "webhook":
        if not settings.WEBHOOK_URL:
            raise ValueError("WEBHOOK_URL must be set when using webhook mode")
        logger.info(
            "Starting bot webhook listener: listen=0.0.0.0:%s, path=/%s, webhook_url=%s/%s",
            settings.PORT,
            _masked_token(settings.TELEGRAM_TOKEN),
            settings.WEBHOOK_URL,
            _masked_token(settings.TELEGRAM_TOKEN),
        )
        await application.updater.start_webhook(
            listen="0.0.0.0",
            port=settings.PORT,
            url_path=settings.TELEGRAM_TOKEN,
            webhook_url=f"{settings.WEBHOOK_URL}/{settings.TELEGRAM_TOKEN}",
        )
        logger.info("Telegram webhook started")
    elif settings.CONNECTION_MODE.lower() == "polling":
        logger.info("Starting bot polling...")
        await application.updater.start_polling()
        logger.info("Telegram polling started")
    else:
        raise ValueError(f"Invalid CONNECTION_MODE: {settings.CONNECTION_MODE}")

    # Start webapp server
    logger.info(
        "Starting webapp server: host=0.0.0.0 port=%s (reverse proxy should target this port)",
        settings.WEBAPP_PORT,
    )
    config = uvicorn.Config(
        webapp,
        host="0.0.0.0",
        port=settings.WEBAPP_PORT,
        log_level=settings.LOG_LEVEL.lower(),
    )
    server = uvicorn.Server(config)

    try:
        logger.info("Uvicorn server entering serve loop")
        await server.serve()
    finally:
        logger.info("Shutting down...")
        if application.updater.running:
            logger.info("Stopping Telegram updater...")
            await application.updater.stop()
        logger.info("Stopping Telegram application...")
        await application.stop()
        logger.info("Shutting down Telegram application...")
        await application.shutdown()
        logger.info("=== ifly-time-bot shutdown complete ===")


if __name__ == '__main__':
    asyncio.run(main())
