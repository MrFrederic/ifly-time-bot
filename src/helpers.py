import asyncio
import logging
import re
from datetime import date, datetime
from telegram import Update
from telegram.error import TelegramError, BadRequest, Forbidden, NetworkError
from .config import settings
from telegram.ext import ContextTypes
from .database import Request, SessionLocal
from .messages import Messages

logger = logging.getLogger(__name__)

def escape_markdown(text: str) -> str:
    """Escape special Markdown characters to prevent parsing errors."""
    # Characters that need escaping in Telegram Markdown: _ * [ ] ( ) ~ ` > # + - = | { } . !
    # For basic Markdown mode, the main ones are: _ * ` [
    escape_chars = r'_*`\['
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

async def check_group(update: Update):
    """Check if message is from the allowed group."""
    if update.message is None:
        logger.warning(f"check_group called with no message in update")
        return False
    if update.message.chat.id != settings.ALLOWED_GROUP_ID or update.message.message_thread_id != settings.THREAD_ID:
        logger.warning(
            f"Unauthorized access attempt: user_id={update.effective_user.id if update.effective_user else 'unknown'}, "
            f"chat_id={update.message.chat.id}, thread_id={update.message.message_thread_id}"
        )
        return False
    return True

def parse_user_date(text: str) -> date:
    today = datetime.now(settings.tz).date()
    try:
        return datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        pass
    
    try:
        dt = datetime.strptime(text, "%d.%m")
        candidate = dt.replace(year=today.year).date()
        if candidate < today:
             candidate = candidate.replace(year=today.year + 1)
        return candidate
    except ValueError:
        logger.warning(f"Failed to parse user date input: '{text}'")
        raise ValueError("Invalid format")

async def delete_command_message(update: Update):
    """Delete the command message to keep chat clean."""
    try:
        if update.message:
            await update.message.delete()
        elif update.callback_query and update.callback_query.message:
            await update.callback_query.message.delete()
    except Forbidden as e:
        logger.warning(f"Bot lacks permission to delete message: {e}")
    except BadRequest as e:
        logger.warning(f"Failed to delete message (may be too old or already deleted): {e}")
    except NetworkError as e:
        logger.error(f"Network error while deleting message: {e}")
    except TelegramError as e:
        logger.error(f"Telegram API error while deleting message: {e}")

async def is_user_in_chat(bot, user_id: int, group_id: int, max_retries: int = 3) -> bool:
    """Check if a user is still a member of the chat. Retries on transient errors."""
    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            member = await bot.get_chat_member(group_id, user_id)
            # ChatMemberStatus: 'left', 'kicked' means user is not in chat
            if member.status in ['left', 'kicked']:
                logger.info(f"User {user_id} confirmed as '{member.status}' in group {group_id}.")
                return False
            return True
        except Forbidden as e:
            logger.warning(f"Bot not authorized to check membership for user_id={user_id}: {e}")
            return True  # Assume user is in chat if we can't check
        except BadRequest as e:
            error_msg = str(e).lower()
            # "user not found" is a definitive signal that the user doesn't exist
            if "user not found" in error_msg:
                logger.info(f"User {user_id} definitively not found in group {group_id}: {e}")
                return False
            # Other BadRequest errors (like Participant_id_invalid) can be transient
            last_exception = e
            logger.warning(
                f"BadRequest checking user {user_id} in group {group_id} "
                f"(attempt {attempt}/{max_retries}): {e}"
            )
        except (NetworkError, TelegramError) as e:
            last_exception = e
            logger.warning(
                f"Error checking user {user_id} in group {group_id} "
                f"(attempt {attempt}/{max_retries}): {type(e).__name__}: {e}"
            )

        if attempt < max_retries:
            delay = 2 ** attempt  # exponential backoff: 2s, 4s
            logger.info(f"Retrying is_user_in_chat for user {user_id} in {delay}s...")
            await asyncio.sleep(delay)

    # All retries exhausted — assume user is still in chat to avoid false deletions
    logger.error(
        f"All {max_retries} attempts to check user {user_id} in group {group_id} failed. "
        f"Last error: {last_exception}. Assuming user is still in chat."
    )
    return True

async def get_user_display_name(bot, user_id: int, group_id: int, ping: bool = True, escape_md: bool = True) -> str:
    try:
        member = await bot.get_chat_member(group_id, user_id)
        user = member.user
        if user.username:
            username = escape_markdown(user.username) if escape_md else user.username
            return f"{'@' if ping else ''}{username}"
        else:
            full_name = escape_markdown(user.full_name) if escape_md else user.full_name
            return full_name
    except Forbidden as e:
        logger.warning(f"Bot not authorized to get chat member info for user_id={user_id}: {e}")
        return str(user_id)
    except BadRequest as e:
        logger.warning(f"User {user_id} not found in group {group_id}: {e}")
        return str(user_id)
    except NetworkError as e:
        logger.error(f"Network error while fetching user {user_id} display name: {e}")
        return str(user_id)
    except TelegramError as e:
        logger.error(f"Telegram API error while fetching user {user_id} display name: {e}")
        return str(user_id)
    
def format_hours(min_hours: float, max_hours: float) -> str:
    if min_hours == max_hours:
        return f"{min_hours:g}ч"
    return f"{min_hours:g}-{max_hours:g}ч"

# Cache for the request list text
REQUEST_LIST_CACHE = None
REQUEST_LIST_CACHE_DATE = None

def invalidate_request_cache():
    global REQUEST_LIST_CACHE, REQUEST_LIST_CACHE_DATE
    REQUEST_LIST_CACHE = None
    REQUEST_LIST_CACHE_DATE = None

async def list_requests(context: ContextTypes.DEFAULT_TYPE) -> str:
    global REQUEST_LIST_CACHE, REQUEST_LIST_CACHE_DATE
    
    today = datetime.now(settings.tz).date()
    if REQUEST_LIST_CACHE is not None and REQUEST_LIST_CACHE_DATE == today:
        return REQUEST_LIST_CACHE

    db = SessionLocal()
    try:
        requests = db.query(Request).filter(Request.status == 'pending').all()
    except Exception as e:
        logger.error(f"Database error while fetching pending requests: {e}")
        db.close()
        return None
    db.close()
        
    now = datetime.now(settings.tz).date()
    today_requests = []
    future_requests = []

    for req in requests:
        if req.target_date is None or req.target_date <= now:
            today_requests.append(req)
        else:
            future_requests.append(req)

    if not today_requests and not future_requests:
        return None

    # Sort today requests: max_hours desc
    today_requests.sort(key=lambda x: x.max_hours, reverse=True)

    # Sort future requests: date asc, then max_hours desc
    future_requests.sort(key=lambda x: x.max_hours, reverse=True)
    future_requests.sort(key=lambda x: x.target_date)

    msg = ""
    if today_requests:
        msg += Messages.MSG_CURRENT_REQUESTS_HEADER
    
        for req in today_requests:
            display_name = await get_user_display_name(context.bot, req.user_id, settings.ALLOWED_GROUP_ID, ping=False, escape_md=False)
            msg += f"\n- `{display_name}`: {format_hours(req.min_hours, req.max_hours)}"

    if future_requests:
        msg += "\n"
        current_date = None
        for req in future_requests:
            d = req.target_date
            if d != current_date:
                msg += f"\n📅 *{d.strftime('%d %b')}*"
                current_date = d
            
            display_name = await get_user_display_name(context.bot, req.user_id, settings.ALLOWED_GROUP_ID, ping=False, escape_md=False)
            msg += f"\n- `{display_name}`: {format_hours(req.min_hours, req.max_hours)}"
    
    REQUEST_LIST_CACHE = msg
    REQUEST_LIST_CACHE_DATE = today
    return msg