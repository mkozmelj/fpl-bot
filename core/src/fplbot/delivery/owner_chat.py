"""The owner's private chat with the bot, for jobs that send more than a text (the backup)."""

from telegram import Bot, InputFile, InputMediaDocument
from telegram.error import BadRequest


class TelegramOwnerChat:
    def __init__(self, bot: Bot, owner_id: int) -> None:
        self._bot = bot
        self._owner_id = owner_id

    async def send_text(self, text: str) -> None:
        await self._bot.send_message(self._owner_id, text)

    async def send_document(self, filename: str, content: bytes, caption: str) -> int:
        message = await self._bot.send_document(
            self._owner_id, InputFile(content, filename=filename), caption=caption
        )
        return message.message_id

    async def replace_document(
        self, message_id: int, filename: str, content: bytes, caption: str
    ) -> bool:
        """``False`` if Telegram refuses (the message is gone); network trouble raises."""
        media = InputMediaDocument(InputFile(content, filename=filename), caption=caption)
        try:
            await self._bot.edit_message_media(media, chat_id=self._owner_id, message_id=message_id)
        except BadRequest:
            return False
        return True
