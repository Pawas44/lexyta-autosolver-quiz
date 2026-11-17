"""
SMS Notifier using Fast2SMS Indian gateway.
"""

import requests
import logging
from .base import BaseNotifier

logger = logging.getLogger("Fast2SMSNotifier")

class Fast2SMSNotifier(BaseNotifier):
    def __init__(self, phone: str, api_key: str):
        self.phone = phone.strip()
        self.api_key = api_key.strip()

    def send(self, message: str) -> bool:
        if not self.api_key:
            return False
        try:
            url = "https://www.fast2sms.com/dev/bulkV2"
            headers = {"authorization": self.api_key}
            payload = {
                "route": "q",
                "message": message.replace("*", "")[:160],
                "language": "english",
                "flash": 0,
                "numbers": self.phone
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code == 200 and resp.json().get("return"):
                logger.info(f"Fast2SMS SMS sent to {self.phone}!")
                return True
            return False
        except Exception as e:
            logger.error(f"Fast2SMS error: {e}")
            return False
