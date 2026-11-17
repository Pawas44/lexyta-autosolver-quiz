"""
Telegram Bot Notifier with HTML formatting and plain-text fallback.
"""

import html
import re
import requests
import logging
from .base import BaseNotifier

logger = logging.getLogger("TelegramNotifier")

class TelegramNotifier(BaseNotifier):
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token.strip()
        self.chat_id = chat_id.strip()

    def _format_html(self, text: str) -> str:
        """Converts basic markdown asterisks to HTML tags and safely escapes content."""
        escaped = html.escape(text)
        # Convert *bold* to <b>bold</b>
        return re.sub(r'\*([^*]+)\*', r'<b>\1</b>', escaped)

    def send(self, message: str) -> bool:
        if not (self.bot_token and self.chat_id):
            return False
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        # 1. Attempt formatted HTML send
        try:
            html_text = self._format_html(message)
            payload = {
                "chat_id": self.chat_id,
                "text": html_text,
                "parse_mode": "HTML"
            }
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                logger.info(f"Telegram notification delivered successfully to chat {self.chat_id}.")
                return True
        except Exception as e:
            logger.warning(f"HTML format send failed: {e}")

        # 2. Fallback to raw text without formatting
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": message
            }
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                logger.info(f"Telegram notification delivered (plain-text) to chat {self.chat_id}.")
                return True
            else:
                logger.error(f"Telegram dispatch failed: HTTP {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Telegram dispatch error: {e}")
            return False
