import logging
from datetime import date, timedelta, datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy.orm import Session
from ..database import Request, SessionLocal
from ..jobs import check_matches_and_notify
from ..config import settings
from ..helpers import check_group, parse_user_date, format_hours, invalidate_request_cache, get_user_display_name, delete_command_message
from ..messages import Messages
from .sticky import refresh_sticky_list

logger = logging.getLogger(__name__)

# States
SELECT_DATE, SELECT_HOURS, CONFIRM_REPLACE = range(3)

# Common Ranges
HOUR_OPTIONS = [
    ("1h", Messages.OPT_1H, 1.0, 1.0),
    ("2.5h", Messages.OPT_2_5H, 2.5, 2.5),
    ("3h", Messages.OPT_3H, 3.0, 3.0),
    ("1-2h", Messages.OPT_1_2H, 1.0, 2.0),
    ("2-3h", Messages.OPT_2_3H, 2.0, 3.0),
    ("3-5h", Messages.OPT_3_5H, 3.0, 5.0),
]

async def send_step_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup: InlineKeyboardMarkup = None, prepend_name: bool = True):
    """
    Helper to send or edit a message during the conversation steps.
    Ensures the user is mentioned and manages the bot_message_id.
    """
    user = update.effective_user
    
    full_text = text
    if prepend_name:
        display_name = await get_user_display_name(context.bot, user.id, settings.ALLOWED_GROUP_ID, ping=True)
        full_text = f"{display_name}\n{text}"
    
    bot_msg_id = context.user_data.get('bot_message_id')
    sent_message = None
    
    # 1. Try to edit the callback message if it exists
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text=full_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            context.user_data['bot_message_id'] = update.callback_query.message.message_id
            return
        except Exception as e:
            logger.warning(f"Failed to edit callback message: {e}")

    # 2. Try to edit the previously saved bot_message_id if it exists
    if bot_msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=settings.ALLOWED_GROUP_ID,
                message_id=bot_msg_id,
                text=full_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return
        except Exception as e:
            logger.warning(f"Failed to edit previous message {bot_msg_id}: {e}")

    # 3. Send a new message if all else fails
    try:
        sent_message = await context.bot.send_message(
            chat_id=settings.ALLOWED_GROUP_ID,
            message_thread_id=settings.THREAD_ID,
            text=full_text,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_notification=True
        )
        context.user_data['bot_message_id'] = sent_message.message_id
    except Exception as e:
        logger.error(f"Failed to send message: {e}")

async def cancel_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id if update.effective_user else 'unknown'
    logger.info(f"User {user_id} cancelled setup")
    
    if query:
        try:
            await query.answer()
            if query.message.reply_to_message:
                try:
                    await query.message.reply_to_message.delete()
                except Exception as e:
                    logger.warning(f"Failed to delete reply_to_message during cancel: {e}")
            await query.delete_message()
        except Exception as e:
            logger.warning(f"Failed to clean up messages during cancel_setup: {e}")
    
    context.user_data.pop('bot_message_id', None)
    return ConversationHandler.END

async def start_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_group(update): return ConversationHandler.END
    
    await delete_command_message(update)

    user = update.effective_user
    if not user:
        logger.error("start_buy called with no effective_user")
        return ConversationHandler.END
    
    logger.info(f"User {user.id} started buy flow")
    
    try:
        db = SessionLocal()
        existing_request = db.query(Request).filter(Request.user_id == user.id, Request.status == 'pending').first()
        
        if existing_request:
            logger.info(f"User {user.id} has existing request (id={existing_request.id}), prompting for replacement")
            keyboard = [
                [InlineKeyboardButton(Messages.BTN_YES_REPLACE, callback_data="confirmed")],
                [InlineKeyboardButton(Messages.BTN_CANCEL, callback_data="cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            hours = existing_request.max_hours if existing_request.min_hours == existing_request.max_hours else f"{existing_request.min_hours}h-{existing_request.max_hours}h"
            text = Messages.MSG_EXISTING_REQUEST.format(hours=hours)
            
            await send_step_message(update, context, text, reply_markup)
            db.close()
            return CONFIRM_REPLACE
        db.close()
    except Exception as e:
        logger.error(f"Database error in start_buy for user {user.id}: {e}")
        return ConversationHandler.END
    
    return await show_date_selection(update, context)

async def confirm_replace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "confirmed":
        return await show_date_selection(update, context)
    
    return ConversationHandler.END

async def show_date_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, error_text=None):
    keyboard = [
        [InlineKeyboardButton(Messages.BTN_IMMEDIATE, callback_data="date_today")],
        [InlineKeyboardButton(Messages.BTN_CANCEL, callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = Messages.MSG_SELECT_DATE
    
    if error_text:
        text += f"\n\n{error_text}"
    
    await send_step_message(update, context, text, reply_markup)
    return SELECT_DATE

async def date_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "date_today":
        context.user_data['target_date'] = datetime.now(settings.tz).date()
        return await show_hours_selection(update, context)
    
    return SELECT_DATE

async def custom_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip()
        logger.debug(f"custom_date_handler received: '{text}' from user {update.effective_user.id if update.effective_user else 'unknown'}")
        
        try:
            await update.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete user's date input message: {e}")

        try:
            target_date = parse_user_date(text)
            context.user_data['target_date'] = target_date
            return await show_hours_selection(update, context)
        except ValueError:
            return await show_date_selection(update, context, error_text=Messages.ERR_INVALID_DATE)
    except Exception as e:
        logger.error(f"Unexpected error in custom_date_handler: {e}", exc_info=True)
        return SELECT_DATE

async def show_hours_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, error_text=None):
    target_date = context.user_data.get('target_date')
    if not target_date:
        return await show_date_selection(update, context)
        
    date_str = target_date.strftime('%Y-%m-%d')
    
    keyboard = []
    row = []
    for id, label, _, _ in HOUR_OPTIONS:
        row.append(InlineKeyboardButton(label, callback_data=f"hours_{id}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton(Messages.BTN_CANCEL, callback_data="cancel")])
    
    markup = InlineKeyboardMarkup(keyboard)
    text = Messages.MSG_SELECT_HOURS.format(date_str=date_str)

    if error_text:
        text += f"\n\n{error_text}"
    
    await send_step_message(update, context, text, markup)
    return SELECT_HOURS

async def custom_hours_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.strip().replace(',', '.').replace(' ', '')
        logger.debug(f"custom_hours_handler received: '{text}' from user {update.effective_user.id if update.effective_user else 'unknown'}")
        
        try:
            await update.message.delete()
        except Exception as e:
            logger.debug(f"Could not delete user's hours input message: {e}")

        try:
            if '-' in text:
                parts = text.split('-')
                if len(parts) != 2:
                    raise ValueError
                min_h = float(parts[0])
                max_h = float(parts[1])
            else:
                min_h = float(text)
                max_h = min_h

            if min_h % 0.5 != 0 or max_h % 0.5 != 0:
                 return await show_hours_selection(update, context, error_text=Messages.ERR_HOURS_MULTIPLE)
            
            if min_h > max_h:
                 min_h, max_h = max_h, min_h

            return await request_confirmation(update, context, min_h, max_h)

        except ValueError:
            return await show_hours_selection(update, context, error_text=Messages.ERR_INVALID_HOURS)
    except Exception as e:
        logger.error(f"Unexpected error in custom_hours_handler: {e}", exc_info=True)
        return SELECT_HOURS

async def hours_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    selected_id = data.split("_")[1]
    try:
        min_h, max_h = next((min_h, max_h) for id, _, min_h, max_h in HOUR_OPTIONS if id == selected_id)
    except StopIteration:
        logger.error(f"Invalid hour option selected: {selected_id}")
        return await show_hours_selection(update, context, error_text="Invalid option selected")
    
    return await request_confirmation(update, context, min_h, max_h)

async def request_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, min_h: float, max_h: float):
    target_date = context.user_data.get('target_date')
    user = update.effective_user
    
    if not user:
        logger.error("request_confirmation called with no effective_user")
        return ConversationHandler.END
    
    if not target_date:
        logger.warning(f"request_confirmation called without target_date for user {user.id}")
        return await show_date_selection(update, context)
    
    logger.info(f"User {user.id} confirming request: {min_h}-{max_h}h, date={target_date}")
    
    db = SessionLocal()
    try:
        existing = db.query(Request).filter(
            Request.user_id == user.id,
            Request.status == 'pending'
        ).first()
        if existing:
            logger.info(f"Removing existing request (id={existing.id}) for user {user.id}")
            db.delete(existing)
            db.commit()

        new_req = Request(
            user_id=user.id,
            min_hours=min_h,
            max_hours=max_h,
            target_date=target_date
        )
        db.add(new_req)
        db.commit()
            
        display_name = await get_user_display_name(context.bot, user.id, settings.ALLOWED_GROUP_ID, ping=True)

        success_text = (
            Messages.MSG_REQUEST_SAVED.format(user_name=display_name, hours_str=format_hours(min_h, max_h)) +
            (Messages.MSG_REQUEST_SAVED_DATE.format(date_str=target_date.strftime('%d.%m.%Y')) if target_date and target_date > datetime.now(settings.tz).date() else "") +
            Messages.MSG_REQUEST_SAVED_GROUP +
            Messages.MSG_REQUEST_SAVED_TIP
        )
        
        await send_step_message(update, context, success_text, prepend_name=False)

        # Trigger Matching
        await check_matches_and_notify(context)
        
        # Invalidate cache and force-refresh sticky list to reflect new request
        invalidate_request_cache()
        await refresh_sticky_list(update, context, is_system=True)
            
    except Exception as e:
        logger.error(f"Error saving request for user {user.id}: {e}", exc_info=True)
        error_msg = Messages.ERR_SAVE_REQUEST
        try:
            await send_step_message(update, context, error_msg)
        except Exception as send_err:
            logger.error(f"Failed to send error message to user {user.id}: {send_err}")
    finally:
        db.close()
        context.user_data.pop('bot_message_id', None)

    return ConversationHandler.END
