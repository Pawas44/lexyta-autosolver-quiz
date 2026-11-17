"""
Notification Dispatcher
Coordinates alerts across WhatsApp, Termux, SMS, and Telegram.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Any
from src.core.config import AppConfig
from .whatsapp import WhatsAppNotifier
from .termux import TermuxNotifier
from .sms import Fast2SMSNotifier
from .telegram import TelegramNotifier

logger = logging.getLogger("NotificationDispatcher")

IST = timezone(timedelta(hours=5, minutes=30))

def format_datetime_ist(date_str: Optional[str]) -> str:
    """Converts UTC ISO timestamp from LMS to human-readable Indian Standard Time (IST)."""
    if not date_str:
        return "No Due Date Specified"
    try:
        clean_str = date_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        dt_ist = dt.astimezone(IST)
        # Format: e.g. "18 Nov 2026, 11:59 PM (IST)"
        return dt_ist.strftime("%d %b %Y, %I:%M %p (IST)")
    except Exception:
        return str(date_str)

class NotificationDispatcher:
    def __init__(self, config: AppConfig):
        self.config = config
        self.phone = config.phone_number
        full_phone = f"{config.country_code.replace('+', '')}{config.phone_number}"

        self.notifiers = []

        # 1. Termux (Android Mobile)
        if config.notifications.get("termux", {}).get("enabled", True):
            self.notifiers.append(TermuxNotifier(target_phone=self.phone))

        # 2. WhatsApp (CallMeBot)
        wa_cfg = config.notifications.get("whatsapp_callmebot", {})
        if wa_cfg.get("enabled") and wa_cfg.get("api_key"):
            self.notifiers.append(WhatsAppNotifier(phone=full_phone, api_key=wa_cfg["api_key"]))

        # 3. Fast2SMS
        sms_cfg = config.notifications.get("fast2sms", {})
        if sms_cfg.get("enabled") and sms_cfg.get("api_key"):
            self.notifiers.append(Fast2SMSNotifier(phone=self.phone, api_key=sms_cfg["api_key"]))

        # 4. Telegram
        tg_cfg = config.notifications.get("telegram", {})
        if tg_cfg.get("enabled") and tg_cfg.get("bot_token") and tg_cfg.get("chat_id"):
            self.notifiers.append(TelegramNotifier(bot_token=tg_cfg["bot_token"], chat_id=tg_cfg["chat_id"]))

    def notify_assignment(self, subject: str, assignment_name: str, due_date: Optional[str], details: Optional[str] = None):
        """Dispatches an alert when a new assignment is posted."""
        formatted_due = format_datetime_ist(due_date)
        msg = (
            f"📢 *LMS New Assignment Alert!*\n\n"
            f"📚 *Subject:* {subject}\n"
            f"📝 *Assignment:* {assignment_name}\n"
            f"⏰ *Due Date & Time:* {formatted_due}\n"
        )
        if details:
            msg += f"💡 *Details:* {details[:140]}\n"
        msg += f"\n🌐 Open LMS: https://lms.lexyta.com"

        self._dispatch(msg)

    def notify_quiz_solved(self, subject: str, quiz_name: str, score: Optional[Any] = None):
        """Dispatches an alert when a quiz is automatically solved & submitted."""
        msg = (
            f"🎉 *LMS Quiz Auto-Solved & Submitted!*\n\n"
            f"📚 *Subject:* {subject}\n"
            f"📝 *Quiz:* {quiz_name}\n"
            f"✅ *Status:* Successfully Solved via Gemini AI & Submitted\n"
        )
        if score is not None:
            msg += f"📊 *Score:* {score}\n"
        msg += f"\n🌐 View Result: https://lms.lexyta.com"

        self._dispatch(msg)

    def notify_quiz_grade(self, subject: str, quiz_name: str, grade: float, max_score: Optional[float] = None, graded_by: Optional[str] = None):
        """Dispatches an alert when quiz or assignment marks/grades are released."""
        if max_score and max_score > 0:
            pct = (grade / max_score) * 100
            score_line = f"🎯 *Marks:* {grade} / {max_score} ({pct:.1f}%)\n"
        else:
            score_line = f"🎯 *Marks:* {grade}\n"

        msg = (
            f"📊 *LMS Marks / Result Released!*\n\n"
            f"📚 *Subject:* {subject}\n"
            f"📝 *Item:* {quiz_name}\n"
            f"{score_line}"
        )
        if graded_by:
            msg += f"👨‍🏫 *Evaluated By:* {graded_by}\n"
        msg += f"\n🌐 Check Portal: https://lms.lexyta.com"

        self._dispatch(msg)

    def _dispatch(self, message: str):
        logger.info(f"\n{'='*55}\nALERT FOR {self.phone}:\n{message}\n{'='*55}")
        any_success = False

        for n in self.notifiers:
            try:
                if n.send(message):
                    any_success = True
            except Exception as e:
                logger.error(f"Error in {n.__class__.__name__}: {e}")

        if not any_success and not any(isinstance(n, (WhatsAppNotifier, TermuxNotifier)) for n in self.notifiers):
            logger.info(f"[INFO] Alert logged to console. To receive WhatsApp alerts on {self.phone}, add your free CallMeBot key in config/config.json.")
