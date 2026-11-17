"""
Android Termux Native Notifier.
Sends local push notifications and native SMS directly from phone's SIM to 9315135782.
Requires zero external API keys!
"""

import shutil
import subprocess
import logging
from .base import BaseNotifier

logger = logging.getLogger("TermuxNotifier")

class TermuxNotifier(BaseNotifier):
    def __init__(self, target_phone: str = "9315135782"):
        self.target_phone = target_phone

    def send(self, message: str) -> bool:
        has_notif = shutil.which("termux-notification") is not None
        has_sms = shutil.which("termux-sms-send") is not None

        if not (has_notif or has_sms):
            return False

        success = False
        # 1. Native Push Notification
        if has_notif:
            try:
                subprocess.run([
                    "termux-notification",
                    "--title", "LMS Lexyta Alert",
                    "--content", message,
                    "--priority", "high"
                ], check=True)
                logger.info("Sent native Termux status bar notification!")
                success = True
            except Exception as e:
                logger.warning(f"Termux notification failed: {e}")

        # 2. Native SMS from SIM (if phone provided)
        if has_sms and self.target_phone:
            try:
                plain = message.replace("*", "")
                subprocess.run([
                    "termux-sms-send",
                    "-n", self.target_phone,
                    plain
                ], check=True)
                logger.info(f"Sent native SMS via Termux to {self.target_phone}!")
                success = True
            except Exception as e:
                logger.warning(f"Termux SMS failed: {e}")

        return success
