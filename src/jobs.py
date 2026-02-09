import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from .database import SessionLocal, Request
from .matching import check_and_process_matches
from .config import settings
from .messages import Messages
from .helpers import get_user_display_name, invalidate_request_cache, is_user_in_chat
from .handlers.sticky import refresh_sticky_list

logger = logging.getLogger(__name__)

async def cleanup_orphaned_requests(context: ContextTypes.DEFAULT_TYPE, db) -> int:
    """
    Removes requests from users who have left the chat.
    Returns the number of deleted requests.
    """
    deleted_count = 0
    try:
        pending_requests = db.query(Request).filter(Request.status == 'pending').all()
        for req in pending_requests:
            if not await is_user_in_chat(context.bot, req.user_id, settings.ALLOWED_GROUP_ID):
                logger.warning(f"User {req.user_id} has left the chat. Deleting their request (id={req.id}).")
                db.delete(req)
                deleted_count += 1
        if deleted_count > 0:
            db.commit()
            invalidate_request_cache()
            logger.info(f"Cleaned up {deleted_count} orphaned request(s) from users who left the chat.")
    except Exception as e:
        logger.error(f"Error during orphaned request cleanup: {e}", exc_info=True)
        db.rollback()
    return deleted_count

async def check_matches_and_notify(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Checks for matches for today (including backlog) and notifies the group if found.
    Returns True if a match was found and notified.
    """
    db = SessionLocal()
    try:
        # First, clean up requests from users who have left the chat
        await cleanup_orphaned_requests(context, db)
        
        match = check_and_process_matches(db)

        if match:
            logger.info(f"Match found with {len(match)} users, preparing notification")
            # Notify Group
            users_lines = []
            for r in match:
                display_name = await get_user_display_name(context.bot, r.user_id, settings.ALLOWED_GROUP_ID)
                users_lines.append(f"- {display_name} ({r.min_hours}-{r.max_hours}ч)")
            
            users_text = "\n".join(users_lines)
            try:
                await context.bot.send_message(
                    chat_id=settings.ALLOWED_GROUP_ID,
                    message_thread_id=settings.THREAD_ID,
                    text=Messages.MSG_GROUP_FOUND.format(users_text=users_text),
                    parse_mode='Markdown'
                )
                logger.info("Match notification sent successfully")
            except Exception as e:
                logger.error(f"Failed to send match notification to group: {e}")
                return False
            
            # Invalidate cache and refresh sticky list as requests are removed
            invalidate_request_cache()
            try:
                await refresh_sticky_list(update = None, context = context, is_system = True)
            except Exception as e:
                logger.warning(f"Failed to refresh sticky list after match: {e}")
            
            return True
        return False
    except Exception as e:
        logger.error(f"Error in check_matches_and_notify: {e}", exc_info=True)
        return False
    finally:
        db.close()

async def run_daily_matching_job(context: ContextTypes.DEFAULT_TYPE):
    """
    Job that runs daily to check for matches.
    """
    logger.info("Running daily matching job...")
    matches_found = 0
    
    # Keep checking until no more matches found
    try:
        while True:
            found = await check_matches_and_notify(context)
            if not found:
                break
            matches_found += 1
        
        logger.info(f"Daily matching job completed: {matches_found} matches found")
    except Exception as e:
        logger.error(f"Error during daily matching job: {e}", exc_info=True)
    
    # Refresh sticky list because date changed and "today" requests might be different
    invalidate_request_cache()
    try:
        await refresh_sticky_list(update = None, context = context, is_system=True)
    except Exception as e:
        logger.warning(f"Failed to refresh sticky list after daily job: {e}")

async def manual_matching_command(update: 'Update', context: ContextTypes.DEFAULT_TYPE):
    """
    Command handler to manually trigger the matching job.
    """
    user_id = update.effective_user.id if update.effective_user else 'unknown'
    logger.info(f"Manual matching triggered by user {user_id}")
    
    try:
        await run_daily_matching_job(context)
        await context.bot.send_message(chat_id=settings.ALLOWED_GROUP_ID, message_thread_id=settings.THREAD_ID, text="Matching job completed.", disable_notification=True)
    except Exception as e:
        logger.error(f"Error in manual matching command: {e}", exc_info=True)
        try:
            await context.bot.send_message(chat_id=settings.ALLOWED_GROUP_ID, message_thread_id=settings.THREAD_ID, text="Error during matching job. Check logs for details.", disable_notification=True)
        except Exception as send_error:
            logger.error(f"Failed to send error message to group: {send_error}")