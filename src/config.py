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
    
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
    
    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.TIMEZONE)

settings = Settings()
