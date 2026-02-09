import logging
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, DateTime, BigInteger
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import SQLAlchemyError, OperationalError, IntegrityError
from datetime import datetime
from .config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

class Request(Base):
    __tablename__ = 'requests'

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    min_hours = Column(Float, nullable=False)
    max_hours = Column(Float, nullable=False)
    target_date = Column(Date, nullable=False)
    status = Column(String, default='pending')  # 'pending', 'matched'
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Request(user_id={self.user_id}, hours={self.min_hours}-{self.max_hours}, date={self.target_date})>"


class BotState(Base):
    """Stores persistent bot state like last sticky message info."""
    __tablename__ = 'bot_state'

    key = Column(String, primary_key=True)
    value = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<BotState(key={self.key}, value={self.value})>"


try:
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    logger.error(f"Failed to create database engine: {e}")
    raise


def get_bot_state(key: str) -> str | None:
    """Get a bot state value from the database."""
    db = SessionLocal()
    try:
        state = db.query(BotState).filter(BotState.key == key).first()
        return state.value if state else None
    except SQLAlchemyError as e:
        logger.error(f"Error getting bot state '{key}': {e}")
        return None
    finally:
        db.close()


def set_bot_state(key: str, value: str | None) -> bool:
    """Set a bot state value in the database."""
    db = SessionLocal()
    try:
        state = db.query(BotState).filter(BotState.key == key).first()
        if state:
            state.value = value
            state.updated_at = datetime.utcnow()
        else:
            state = BotState(key=key, value=value)
            db.add(state)
        db.commit()
        return True
    except SQLAlchemyError as e:
        logger.error(f"Error setting bot state '{key}': {e}")
        db.rollback()
        return False
    finally:
        db.close()


def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except OperationalError as e:
        logger.error(f"Database connection failed during init: {e}")
        raise
    except SQLAlchemyError as e:
        logger.error(f"Failed to create database tables: {e}")
        raise

def get_db():
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()
