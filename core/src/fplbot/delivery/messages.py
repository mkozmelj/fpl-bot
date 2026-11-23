"""Telegram-agnostic message shapes passed between ``telegram.py`` and the conversation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Incoming:
    """A text message in a private chat (where the chat ID equals the sender's user ID)."""

    chat_id: int
    user_id: int
    text: str


@dataclass(frozen=True)
class Press:
    """A tap on an inline keyboard button in a private chat. ``data`` is the button's
    ``Button.data`` exactly as the conversation produced it."""

    chat_id: int
    user_id: int
    data: str


@dataclass(frozen=True)
class Button:
    label: str
    data: str  # at most 64 bytes (Telegram's callback_data limit)


@dataclass(frozen=True)
class Reply:
    text: str
    # Inline keyboard: rows of buttons. Empty for a plain message.
    keyboard: tuple[tuple[Button, ...], ...] = ()
