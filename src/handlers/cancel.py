import logging
from telegram import Update
from telegram.ext import ContextTypes
from ..database import Request, SessionLocal
from ..helpers import check_group, invalidate_request_cache, delete_command_message, get_user_display_name
from ..messages import Messages
from ..config import settings
from .sticky import refresh_sticky_list

logger = logging.getLogger(__name__)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group(update): return
    await delete_command_message(update)
    
    user = update.effective_user
    if not user:
        logger.error("cancel_command called with no effective_user")
        return
    
    db = SessionLocal()
    try:
        request = db.query(Request).filter(Request.user_id == user.id, Request.status == 'pending').first()
        
        display_name = await get_user_display_name(context.bot, user.id, settings.ALLOWED_GROUP_ID, ping=True)
        text = f"{display_name}\n"

        if request:
            try:
                db.delete(request)
                db.commit()
                logger.info(f"User {user.id} cancelled their request (request_id={request.id})")
                await context.bot.send_message(chat_id=settings.ALLOWED_GROUP_ID, message_thread_id=settings.THREAD_ID, text=text+Messages.MSG_CANCELLED, disable_notification=True)
            except Exception as e:
                logger.error(f"Database error while cancelling request for user {user.id}: {e}")
                db.rollback()
                return
        else:
            logger.info(f"User {user.id} tried to cancel but has no active request")
            await context.bot.send_message(chat_id=settings.ALLOWED_GROUP_ID, message_thread_id=settings.THREAD_ID, text=text+Messages.MSG_NO_ACTIVE_REQUEST, disable_notification=True)
    except Exception as e:
        logger.error(f"Error in cancel_command for user {user.id}: {e}", exc_info=True)
    finally:
        db.close()
    
    invalidate_request_cache()
    try:
        await refresh_sticky_list(update, context)
    except Exception as e:
        logger.warning(f"Failed to refresh sticky list after cancel: {e}")
