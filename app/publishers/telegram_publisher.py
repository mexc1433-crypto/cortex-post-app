"""Telegram channel publisher."""
import logging
from typing import Optional

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError

from app.publishers.base import BasePublisher
from app.config import settings

logger = logging.getLogger(__name__)


class TelegramPublisher(BasePublisher):
    platform = "telegram"
    
    def __init__(self):
        self._bot: Optional[Bot] = None
    
    def set_bot(self, bot: Bot):
        """Set the bot instance (called during startup)."""
        self._bot = bot
    
    async def publish(
        self,
        channel_telegram_id: int,
        content: str,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True,
        **kwargs,
    ) -> int | None:
        """
        Publish a message to a Telegram channel.
        
        Args:
            channel_telegram_id: The channel's Telegram ID
            content: Message content
            parse_mode: HTML, Markdown, or MarkdownV2
            disable_web_page_preview: Disable link previews
        
        Returns:
            Message ID on success
        """
        if not self._bot:
            raise RuntimeError("Bot instance not set. Call set_bot() first.")
        
        try:
            # Map parse mode string to enum
            parse_mode_enum = ParseMode.HTML
            if parse_mode == "Markdown":
                parse_mode_enum = ParseMode.MARKDOWN
            elif parse_mode == "MarkdownV2":
                parse_mode_enum = ParseMode.MARKDOWN_V2
            
            message = await self._bot.send_message(
                chat_id=channel_telegram_id,
                text=content,
                parse_mode=parse_mode_enum,
                disable_web_page_preview=disable_web_page_preview,
            )
            
            logger.info(f"Message sent to channel {channel_telegram_id}, msg_id={message.message_id}")
            return message.message_id
        
        except TelegramAPIError as e:
            logger.error(f"Telegram publish error: {e}")
            raise
    
    async def delete(self, message_id: int, channel_telegram_id: int, **kwargs) -> bool:
        """Delete a message from a channel."""
        if not self._bot:
            raise RuntimeError("Bot instance not set")
        
        try:
            await self._bot.delete_message(
                chat_id=channel_telegram_id,
                message_id=message_id,
            )
            return True
        except TelegramAPIError as e:
            logger.error(f"Telegram delete error: {e}")
            return False
    
    async def edit(
        self,
        channel_telegram_id: int,
        message_id: int,
        content: str,
        parse_mode: str = "HTML",
    ) -> bool:
        """Edit an existing message."""
        if not self._bot:
            raise RuntimeError("Bot instance not set")
        
        try:
            parse_mode_enum = ParseMode.HTML
            if parse_mode == "Markdown":
                parse_mode_enum = ParseMode.MARKDOWN
            elif parse_mode == "MarkdownV2":
                parse_mode_enum = ParseMode.MARKDOWN_V2
            
            await self._bot.edit_message_text(
                chat_id=channel_telegram_id,
                message_id=message_id,
                text=content,
                parse_mode=parse_mode_enum,
            )
            return True
        except TelegramAPIError as e:
            logger.error(f"Telegram edit error: {e}")
            return False


telegram_publisher = TelegramPublisher()
