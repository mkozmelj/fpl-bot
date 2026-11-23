"""python-telegram-bot wiring: the only place that knows about Telegram updates.

Only text messages in private chats are handled; groups, channels and edits are ignored
entirely. Errors are logged by type only, because exception messages can carry chat IDs.
"""

import logging
from typing import Any

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from fplbot.delivery.conversation import Conversation, Incoming

log = logging.getLogger(__name__)


def install(
    application: Application[Any, Any, Any, Any, Any, Any], conversation: Conversation
) -> None:
    async def on_private_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message, user = update.message, update.effective_user
        if message is None or message.text is None or user is None:
            return
        incoming = Incoming(chat_id=message.chat_id, user_id=user.id, text=message.text)
        for reply in await conversation.respond(incoming, context.bot.username):
            await context.bot.send_message(message.chat_id, reply.text)

    async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        log.error("update handling failed: %s", type(context.error).__name__)

    application.add_handler(
        MessageHandler(
            filters.UpdateType.MESSAGE & filters.ChatType.PRIVATE & filters.TEXT,
            on_private_text,
        )
    )
    application.add_error_handler(on_error)
