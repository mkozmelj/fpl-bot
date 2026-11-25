"""python-telegram-bot wiring: the only place that knows about Telegram updates.

Only text messages and inline-button presses in private chats are handled; groups, channels and
edits are ignored entirely. Errors are logged by type only, because exception messages can carry
chat IDs.
"""

import logging
from typing import Any

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from fplbot.delivery.conversation import Conversation, Incoming, Press, Reply

log = logging.getLogger(__name__)


def install(
    application: Application[Any, Any, Any, Any, Any, Any], conversation: Conversation
) -> None:
    async def on_private_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message, user = update.message, update.effective_user
        if message is None or message.text is None or user is None:
            return
        incoming = Incoming(chat_id=message.chat_id, user_id=user.id, text=message.text)
        await _send(
            context, message.chat_id, await conversation.respond(incoming, context.bot.username)
        )

    async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query, chat, user = update.callback_query, update.effective_chat, update.effective_user
        if query is None or chat is None or user is None or chat.type != ChatType.PRIVATE:
            return
        await query.answer()  # stops the button's loading spinner
        if not isinstance(query.data, str):
            return
        press = Press(chat_id=chat.id, user_id=user.id, data=query.data)
        await _send(context, chat.id, await conversation.press(press))

    async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        log.error("update handling failed: %s", type(context.error).__name__)

    application.add_handler(
        MessageHandler(
            filters.UpdateType.MESSAGE & filters.ChatType.PRIVATE & filters.TEXT,
            on_private_text,
        )
    )
    application.add_handler(CallbackQueryHandler(on_button))
    application.add_error_handler(on_error)


async def _send(context: ContextTypes.DEFAULT_TYPE, chat_id: int, replies: list[Reply]) -> None:
    await send_replies(context.bot, chat_id, replies)


async def send_replies(bot: Bot, chat_id: int, replies: list[Reply]) -> None:
    """Send ``replies`` (with their inline keyboards) to ``chat_id``, also outside an update."""
    for reply in replies:
        markup = (
            InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton(b.label, callback_data=b.data) for b in row]
                    for row in reply.keyboard
                ]
            )
            if reply.keyboard
            else None
        )
        await bot.send_message(chat_id, reply.text, reply_markup=markup)
