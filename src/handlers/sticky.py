from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from ..helpers import list_requests, check_group
from ..messages import Messages
from ..config import settings
from ..database import get_bot_state, set_bot_state
import logging

logger = logging.getLogger(__name__)

# Database keys for sticky message state
STICKY_MESSAGE_ID_KEY = 'sticky_list_message_id'
STICKY_MESSAGE_CONTENT_KEY = 'sticky_list_content'


async def refresh_sticky_list(update: Update, context: ContextTypes.DEFAULT_TYPE, is_system = False):
    """
    Refreshes the sticky list message in the chat.
    - For user messages (is_system=False): Always resend to keep message at bottom (sticky behavior)
    - For system calls (is_system=True): Only update if content has changed
    Stores message ID in database for persistence.
    """
    try:
        if not is_system and update and not await check_group(update): 
            return

        # Generate the list message
        try:
            text = await list_requests(context)
        except Exception as e:
            logger.error(f"Failed to generate request list for sticky message: {e}")
            text = None
        
        if not text:
            text = Messages.MSG_NO_REQUESTS

        # Get the last message ID and content from database
        last_msg_id_str = get_bot_state(STICKY_MESSAGE_ID_KEY)
        last_msg_id = int(last_msg_id_str) if last_msg_id_str else None
        last_content = get_bot_state(STICKY_MESSAGE_CONTENT_KEY)

        content_changed = last_content != text

        # For system calls, skip if content unchanged
        if is_system and not content_changed and last_msg_id:
            logger.debug("Sticky list content unchanged (system call), skipping update")
            return

        # For system calls with changed content, try to edit existing message first
        if is_system and content_changed and last_msg_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=settings.ALLOWED_GROUP_ID,
                    message_id=last_msg_id,
                    text=text,
                    parse_mode='Markdown'
                )
                # Update stored content
                set_bot_state(STICKY_MESSAGE_CONTENT_KEY, text)
                logger.info(f"Successfully edited sticky message {last_msg_id}")
                return
            except BadRequest as e:
                # Message might have been deleted or is too old to edit
                logger.warning(f"Could not edit old sticky message {last_msg_id}: {e}")
                # Fall through to send a new message
            except Exception as e:
                logger.error(f"Unexpected error editing sticky message {last_msg_id}: {e}")
                # Fall through to send a new message

        # For user messages: always resend to keep sticky (at bottom)
        # For system calls: send new message if edit failed or no previous message
        if not is_system:
            logger.debug(f"User message detected, resending sticky list to keep it at bottom")

        # Send a new message
        try:
            sent_msg = await context.bot.send_message(
                chat_id=settings.ALLOWED_GROUP_ID,
                message_thread_id=settings.THREAD_ID,
                text=text, 
                parse_mode='Markdown', 
                disable_notification=True
            )
            # Store the new message ID and content in database
            set_bot_state(STICKY_MESSAGE_ID_KEY, str(sent_msg.message_id))
            set_bot_state(STICKY_MESSAGE_CONTENT_KEY, text)
            logger.info(f"Sent new sticky message with id={sent_msg.message_id}")
            
            # Delete old message if it exists
            if last_msg_id:
                try:
                    await context.bot.delete_message(chat_id=settings.ALLOWED_GROUP_ID, message_id=last_msg_id)
                    logger.debug(f"Deleted old sticky message {last_msg_id}")
                except BadRequest as e:
                    logger.warning(f"Could not delete old sticky message {last_msg_id}: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error deleting old sticky message {last_msg_id}: {e}")
        except BadRequest as e:
            logger.error(f"Bad request while sending sticky message: {e}")
        except Exception as e:
            logger.error(f"Error sending sticky message: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error in refresh_sticky_list: {e}", exc_info=True)
