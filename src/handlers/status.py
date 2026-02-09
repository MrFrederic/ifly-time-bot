import logging
from telegram import Update
from telegram.ext import ContextTypes
from ..helpers import check_group, list_requests
from ..messages import Messages
from ..config import settings

logger = logging.getLogger(__name__)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group(update): return
    
    user_id = update.effective_user.id if update.effective_user else 'unknown'
    logger.info(f"User {user_id} requested status")
    
    try:
        msg = await list_requests(context)
        
        if not msg:
            await context.bot.send_message(chat_id=settings.ALLOWED_GROUP_ID, message_thread_id=settings.THREAD_ID, text=Messages.MSG_NO_REQUESTS, disable_notification=True)
            return
        
        await context.bot.send_message(chat_id=settings.ALLOWED_GROUP_ID, message_thread_id=settings.THREAD_ID, text=msg, parse_mode='Markdown', disable_notification=True)
    except Exception as e:
        logger.error(f"Error in status_command: {e}", exc_info=True)
