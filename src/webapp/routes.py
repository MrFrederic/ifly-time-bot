import logging
from datetime import datetime, date
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel, field_validator
from typing import Optional

from ..config import settings
from ..database import SessionLocal, Request as DBRequest
from ..helpers import invalidate_request_cache
from ..jobs import check_matches_and_notify
from ..handlers.sticky import refresh_sticky_list
from .auth import validate_init_data, get_user_id_from_init_data

logger = logging.getLogger(__name__)

router = APIRouter()


class WebAppContext:
    """Minimal context wrapper so existing bot functions can use context.bot."""
    def __init__(self, bot):
        self.bot = bot


def get_bot():
    from .app import _application
    return _application.bot


async def get_current_user(request: Request) -> int:
    """Validate initData from Authorization header and return user_id."""
    auth = request.headers.get('Authorization', '')
    if auth.startswith('tma '):
        init_data = auth[4:]
    else:
        raise HTTPException(status_code=401, detail="Missing initData")

    validated = validate_init_data(init_data, settings.TELEGRAM_TOKEN)
    if not validated:
        raise HTTPException(status_code=401, detail="Invalid initData")

    # Verify the mini-app was opened via the pinned-message button
    start_param = validated.get('start_param')
    if start_param != settings.miniapp_token:
        raise HTTPException(
            status_code=403,
            detail="Откройте приложение через кнопку в чате",
        )

    user_id = get_user_id_from_init_data(validated)
    if not user_id:
        raise HTTPException(status_code=401, detail="No user in initData")

    return user_id


class RequestCreate(BaseModel):
    min_hours: float
    max_hours: float
    target_date: Optional[str] = None  # ISO format YYYY-MM-DD, or null for today

    @field_validator('min_hours', 'max_hours')
    @classmethod
    def validate_hours(cls, v):
        if v < 1.0:
            raise ValueError('Minimum is 1.0 hour')
        if v % 0.5 != 0:
            raise ValueError('Must be a multiple of 0.5')
        return v


@router.get('/request')
async def get_request(user_id: int = Depends(get_current_user)):
    """Get the current user's pending request."""
    db = SessionLocal()
    try:
        req = db.query(DBRequest).filter(
            DBRequest.user_id == user_id,
            DBRequest.status == 'pending'
        ).first()

        if not req:
            return {'request': None}

        return {
            'request': {
                'id': req.id,
                'min_hours': req.min_hours,
                'max_hours': req.max_hours,
                'target_date': req.target_date.isoformat() if req.target_date else None,
                'created_at': req.created_at.isoformat() if req.created_at else None,
            }
        }
    finally:
        db.close()


@router.post('/request')
async def save_request(
    data: RequestCreate,
    user_id: int = Depends(get_current_user),
    bot=Depends(get_bot),
):
    """Create or update (in place) the user's request, then run matching."""
    if data.target_date:
        try:
            target_date = date.fromisoformat(data.target_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
        today = datetime.now(settings.tz).date()
        if target_date < today:
            raise HTTPException(status_code=400, detail="Date cannot be in the past")
    else:
        target_date = datetime.now(settings.tz).date()

    min_h, max_h = data.min_hours, data.max_hours
    if min_h > max_h:
        min_h, max_h = max_h, min_h

    db = SessionLocal()
    try:
        existing = db.query(DBRequest).filter(
            DBRequest.user_id == user_id,
            DBRequest.status == 'pending'
        ).first()

        if existing:
            existing.min_hours = min_h
            existing.max_hours = max_h
            existing.target_date = target_date
            db.commit()
            logger.info(f"Updated request {existing.id} for user {user_id}")
        else:
            new_req = DBRequest(
                user_id=user_id,
                min_hours=min_h,
                max_hours=max_h,
                target_date=target_date,
            )
            db.add(new_req)
            db.commit()
            logger.info(f"Created request for user {user_id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving request for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save request")
    finally:
        db.close()

    # Trigger matching and refresh dashboard
    ctx = WebAppContext(bot)
    invalidate_request_cache()
    await check_matches_and_notify(ctx)
    await refresh_sticky_list(update=None, context=ctx, is_system=True)

    return {'ok': True}


@router.delete('/request')
async def cancel_request(
    user_id: int = Depends(get_current_user),
    bot=Depends(get_bot),
):
    """Cancel (delete) the user's pending request."""
    db = SessionLocal()
    try:
        req = db.query(DBRequest).filter(
            DBRequest.user_id == user_id,
            DBRequest.status == 'pending'
        ).first()

        if not req:
            raise HTTPException(status_code=404, detail="No active request")

        db.delete(req)
        db.commit()
        logger.info(f"Cancelled request for user {user_id}")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelling request for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel request")
    finally:
        db.close()

    ctx = WebAppContext(bot)
    invalidate_request_cache()
    await refresh_sticky_list(update=None, context=ctx, is_system=True)

    return {'ok': True}
