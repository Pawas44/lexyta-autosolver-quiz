"""
WhatsApp Notifier using CallMeBot free API.
Direct delivery to user's phone +919315135782.
"""

import requests
import urllib.parse
import logging
from .base import BaseNotifier

logger = logging.getLogger("WhatsAppNotifier")

class WhatsAppNotifier(BaseNotifier):
    def __init__(self, phone: str, api_key: str):
        self.phone = phone.replace("+", "").strip()
        self.api_key = api_key.strip()

    def send(self, message: str) -> bool:
        if not self.api_key:
            return False
        try:
            encoded_text = urllib.parse.quote(message)
            url = f"https://api.callmebot.com/whatsapp.php?phone={self.phone}&text={encoded_text}&apikey={self.api_key}"
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200 and "success" in resp.text.lower():
                logger.info(f"WhatsApp sent to {self.phone} successfully!")
                return True
            logger.warning(f"CallMeBot WhatsApp response: {resp.text}")
            return False
        except Exception as e:
            logger.error(f"WhatsApp dispatch failed: {e}")
            return False
