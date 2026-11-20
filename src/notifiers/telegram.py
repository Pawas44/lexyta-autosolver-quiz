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
        """Standard notification dispatch."""
        msg_id = self.send_message(message)
        return msg_id is not None

    def send_message(self, message: str) -> Optional[int]:
        """Sends message and returns message_id (for live progress editing)."""
        if not (self.bot_token and self.chat_id):
            return None
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        # 1. Attempt formatted HTML send
        try:
            html_text = self._format_html(message) if not ("<b>" in message or "<code>" in message) else message
            payload = {
                "chat_id": self.chat_id,
                "text": html_text,
                "parse_mode": "HTML"
            }
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                msg_id = data.get("result", {}).get("message_id")
                logger.info(f"Telegram notification delivered (msg_id: {msg_id}) to chat {self.chat_id}.")
                return msg_id
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
                data = resp.json()
                return data.get("result", {}).get("message_id")
            else:
                logger.error(f"Telegram dispatch failed: HTTP {resp.status_code} - {resp.text}")
                return None
        except Exception as e:
            logger.error(f"Telegram dispatch error: {e}")
            return None

    def edit_message(self, message_id: int, message: str) -> bool:
        """Edits an existing message in-place for live real-time progress updates."""
        if not (self.bot_token and self.chat_id and message_id):
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/editMessageText"
        html_text = self._format_html(message) if not ("<b>" in message or "<code>" in message) else message

        try:
            payload = {
                "chat_id": self.chat_id,
                "message_id": message_id,
                "text": html_text,
                "parse_mode": "HTML"
            }
            resp = requests.post(url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Could not edit Telegram message {message_id}: {e}")
            return False

def render_progress_bar(completed: int, total: int, width: int = 10) -> str:
    """Generates a visual progress bar e.g. [██████░░░░] 60% (36/60)."""
    if total <= 0:
        return "[░░░░░░░░░░] 0% (0/0)"
    fraction = min(1.0, max(0.0, completed / total))
    filled = int(round(fraction * width))
    bar = "█" * filled + "░" * (width - filled)
    pct = int(round(fraction * 100))
    return f"[{bar}] {pct}% ({completed}/{total})"

def format_quiz_progress_msg(subject: str, quiz_name: str, completed: int, total: int, step_desc: str, student_name: Optional[str] = None) -> str:
    """Formats real-time progress update for Telegram."""
    bar = render_progress_bar(completed, total)
    header = f"👤 <b>Student:</b> {student_name}\n" if student_name else ""
    return (
        f"⏳ <b>LMS Quiz In Progress...</b>\n\n"
        f"{header}"
        f"📚 <b>Subject:</b> {subject}\n"
        f"📝 <b>Quiz:</b> {quiz_name}\n"
        f"📊 <b>Progress:</b> {bar}\n"
        f"🤖 <b>Status:</b> {step_desc}\n\n"
        f"🌐 <i>Autonomous Gemini AI Engine</i>"
    )

def format_quiz_submitted_msg(subject: str, quiz_name: str, answered: int, total: int, elapsed_sec: float, student_name: Optional[str] = None) -> str:
    """Formats final submission confirmation for Telegram."""
    s = int(elapsed_sec)
    m, s = divmod(s, 60)
    dur_str = f"{m}m {s}s" if m > 0 else f"{s}s"
    header = f"👤 <b>Student:</b> {student_name}\n" if student_name else ""
    return (
        f"🎉 <b>LMS Quiz Solved & Submitted!</b>\n\n"
        f"{header}"
        f"📚 <b>Subject:</b> {subject}\n"
        f"📝 <b>Quiz:</b> {quiz_name}\n"
        f"✅ <b>Answered:</b> {answered} / {total} questions (100%)\n"
        f"⏱️ <b>Time Recorded on LMS:</b> {dur_str} (Stealth Human Pacing 🛡️)\n"
        f"🎯 <b>Status:</b> SUBMITTED & RECORDED\n\n"
        f"🌐 https://lms.lexyta.com"
    )
