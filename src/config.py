import hashlib

from pydantic_settings import BaseSettings
from typing import Optional
from zoneinfo import ZoneInfo

class Settings(BaseSettings):
    TELEGRAM_TOKEN: str
    ALLOWED_GROUP_ID: int
    DATABASE_URL: str
    CONNECTION_MODE: str = "polling"  # "polling" or "webhook"
    THREAD_ID: int = 1
    TIMEZONE: str = "Europe/Minsk"
    
    # Webhook specific
    WEBHOOK_URL: Optional[str] = None
    PORT: int = 8443
    
    # Mini-app
    WEBAPP_PORT: int = 8080
    MINIAPP_URL: str  # t.me deep link to the mini-app, e.g. https://t.me/bot/app

    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
    
    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.TIMEZONE)

    @property
    def miniapp_token(self) -> str:
        """Stable secret derived from the bot token, passed as startapp param."""
        return hashlib.sha256(
            f"ifly-miniapp-{self.TELEGRAM_TOKEN}".encode()
        ).hexdigest()[:32]

settings = Settings()
