"""
Interactive Multi-Tenant Telegram Bot Service
Onboards students via interactive Telegram chat, verifies LMS credentials,
and manages notification routing.
"""

import os
import re
import html
import time
import logging
import requests
from typing import Dict, Any, Optional

from src.core.user_manager import UserManager
from src.client.lexyta_api import LexytaAPIClient
from src.core.config import DEFAULT_GEMINI_KEY

logger = logging.getLogger("TelegramServer")

MASTER_BOT_TOKEN = "9266694753:AAG3ipGnDEhZQqDNz0MQJd2n2yHRoYrQ9Mk"

# Conversation State Enums
STATE_IDLE = "IDLE"
STATE_WAITING_EMAIL = "WAITING_EMAIL"
STATE_WAITING_PASSWORD = "WAITING_PASSWORD"
STATE_WAITING_GEMINI = "WAITING_GEMINI"
STATE_WAITING_SEMESTER = "WAITING_SEMESTER"

class TelegramServer:
    def __init__(self, bot_token: str = None, user_manager: UserManager = None):
        self.bot_token = (bot_token or os.getenv("MASTER_BOT_TOKEN") or MASTER_BOT_TOKEN).strip()
        self.user_manager = user_manager or UserManager()
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        self.states: Dict[int, str] = {}
        self.drafts: Dict[int, Dict[str, Any]] = {}
        self.running = False
        self.on_demand_scanner = None  # Injected multi-scanner callback

    def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML") -> bool:
        """Sends message to a Telegram chat safely."""
        try:
            url = f"{self.base_url}/sendMessage"
            escaped_text = text
            if parse_mode == "HTML":
                # Convert markdown *bold* to <b>bold</b> if present
                escaped_text = re.sub(r'\*([^*]+)\*', r'<b>\1</b>', text)

            payload = {
                "chat_id": chat_id,
                "text": escaped_text,
                "parse_mode": parse_mode
            }
            resp = requests.post(url, json=payload, timeout=20)
            if resp.status_code == 200:
                return True
            
            # Fallback to plain-text
            payload.pop("parse_mode", None)
            payload["text"] = text
            resp2 = requests.post(url, json=payload, timeout=20)
            return resp2.status_code == 200
        except Exception as e:
            logger.error(f"Error sending message to {chat_id}: {e}")
            return False

    def handle_message(self, message: Dict[str, Any]):
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        text = (message.get("text") or "").strip()
        from_user = message.get("from", {})

        if not chat_id or not text:
            return

        current_state = self.states.get(chat_id, STATE_IDLE)

        # -------------------------------------------------------------
        # GLOBAL COMMANDS
        # -------------------------------------------------------------
        if text.startswith("/"):
            cmd = text.split()[0].lower()

            if cmd in ["/start", "/setup", "/relink"]:
                # Always start fresh onboarding asking for email
                self.states[chat_id] = STATE_WAITING_EMAIL
                self.drafts[chat_id] = {
                    "chat_id": chat_id,
                    "username": from_user.get("username", ""),
                    "first_name": from_user.get("first_name", "")
                }
                welcome_msg = (
                    "🎓 <b>Welcome to Lexyta LMS Auto-Solver & Informer Bot!</b>\n\n"
                    "Main aapka personal academic bot hoon jo automatically:\n"
                    "✅ New Quizzes ko AI se solve karke submit karega\n"
                    "📢 New Assignments aate hi exact time ke sath alert karega\n"
                    "📊 Quiz/Assignment marks aane par result bhejega\n\n"
                    "Chaliye aapka account link karte hain!\n\n"
                    "🔹 <b>Step 1/4:</b> Apna <b>Lexyta LMS Email</b> bhejein:"
                )
                self.send_message(chat_id, welcome_msg)
                return

            elif cmd == "/status":
                user = self.user_manager.get_user(chat_id)
                if not user or not user.get("email"):
                    self.send_message(chat_id, "⚠️ Aapka koi account link nahi hai. Type karein /start apna account connect karne ke liye.")
                    return
                
                status_str = "🟢 Active (Monitoring 24/7)" if user.get("is_active", True) else "🔴 Paused"
                msg = (
                    f"📊 <b>LMS Lexyta Monitoring Status</b>\n\n"
                    f"👤 <b>Student:</b> {user.get('student_name', 'Student')}\n"
                    f"📧 <b>Email:</b> {user.get('email')}\n"
                    f"🎓 <b>Program:</b> {user.get('program_name')}\n"
                    f"🔄 <b>Semester Filter:</b> {user.get('semester_filter', 'auto')}\n"
                    f"⚡ <b>Status:</b> {status_str}\n"
                    f"🕒 <b>Last Scan:</b> {user.get('last_scan_utc', 'Pending first scan')}\n"
                    f"🎯 <b>Solved Quizzes:</b> {len(user.get('solved_quizzes', []))}\n"
                    f"📢 <b>Notified Assignments:</b> {len(user.get('notified_assignments', []))}"
                )
                self.send_message(chat_id, msg)
                return

            elif cmd == "/scan":
                user = self.user_manager.get_user(chat_id)
                if not user or not user.get("email"):
                    self.send_message(chat_id, "⚠️ Aapka koi account link nahi hai. Type karein /start.")
                    return
                self.send_message(chat_id, "🔍 <i>LMS scan shuru ho raha hai... Please wait...</i>")
                if self.on_demand_scanner:
                    res = self.on_demand_scanner(chat_id)
                    self.send_message(chat_id, f"✅ Scan Complete!\nQuizzes solved: {res.get('quizzes', 0)}\nAssignments alerted: {res.get('assignments', 0)}")
                else:
                    self.send_message(chat_id, "✅ On-demand scan queued. Background runner will check within a few moments.")
                return

            elif cmd == "/pause":
                if self.user_manager.set_user_active(chat_id, False):
                    self.send_message(chat_id, "⏸️ Monitoring <b>Paused</b>. Ab koi automatic alerts nahi aayenge. Resume karne ke liye /resume type karein.")
                else:
                    self.send_message(chat_id, "⚠️ Koi account link nahi hai.")
                return

            elif cmd == "/resume":
                if self.user_manager.set_user_active(chat_id, True):
                    self.send_message(chat_id, "▶️ Monitoring <b>Resumed</b>! System 24/7 background check karega.")
                else:
                    self.send_message(chat_id, "⚠️ Koi account link nahi hai.")
                return

            elif cmd == "/unlink" or cmd == "/logout":
                self.user_manager.delete_user(chat_id)
                self.states[chat_id] = STATE_IDLE
                self.send_message(chat_id, "🗑️ Aapka account Lexyta Bot se <b>unlink kar diya gaya hai</b>. Naye account ke liye /start dabayein.")
                return

            elif cmd == "/help":
                help_msg = (
                    "ℹ️ <b>Lexyta Bot Help</b>\n\n"
                    "/start - Connect your Lexyta LMS account\n"
                    "/status - View monitoring status\n"
                    "/scan - Run instant scan pass\n"
                    "/pause - Pause alerts\n"
                    "/resume - Resume alerts\n"
                    "/unlink - Disconnect your credentials\n"
                    "/help - Show this guide"
                )
                self.send_message(chat_id, help_msg)
                return

        # -------------------------------------------------------------
        # ONBOARDING STATE MACHINE
        # -------------------------------------------------------------
        if current_state == STATE_WAITING_EMAIL:
            email = text.strip()
            if "@" not in email or "." not in email:
                self.send_message(chat_id, "❌ Kripya valid email address enter karein (e.g. name@domain.com):")
                return

            self.drafts[chat_id]["email"] = email
            self.states[chat_id] = STATE_WAITING_PASSWORD
            self.send_message(chat_id, f"📧 Email set: <code>{email}</code>\n\n🔹 <b>Step 2/4:</b> Apna <b>Lexyta LMS Password</b> bhejein:\n<i>(Password encrypted store hota hai aur sirf verification ke liye use hoga)</i>")
            return

        elif current_state == STATE_WAITING_PASSWORD:
            password = text.strip()
            email = self.drafts[chat_id].get("email")

            self.send_message(chat_id, "⏳ <i>Lexyta LMS par login verify kiya ja raha hai...</i>")

            # Validate directly with LMS
            try:
                client = LexytaAPIClient(email, password)
                if not client.signin():
                    self.send_message(chat_id, "❌ <b>Login Failed!</b> Lexyta LMS ne credentials reject kar diye.\n\nKripya apna <b>Email dobara bhejein</b>:")
                    self.states[chat_id] = STATE_WAITING_EMAIL
                    return

                profile = client.get_profile() or {}
                programs = client.get_enrolled_programs() or []
                student_name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip() or "Student"
                program_name = programs[0].get("name", "BCA") if programs else "Default"
                program_id = programs[0].get("id", "") if programs else ""

                self.drafts[chat_id]["password"] = password
                self.drafts[chat_id]["student_name"] = student_name
                self.drafts[chat_id]["program_name"] = program_name
                self.drafts[chat_id]["program_id"] = program_id

                self.states[chat_id] = STATE_WAITING_GEMINI
                success_msg = (
                    f"✅ <b>Login Verified!</b>\n\n"
                    f"👤 <b>Student:</b> {student_name}\n"
                    f"🎓 <b>Program:</b> {program_name}\n\n"
                    f"🔹 <b>Step 3/4:</b> Apna <b>Google Gemini API Key</b> bhejein:\n"
                    f"<i>(Agar shared system key use karni hai to type karein: <code>default</code>)</i>"
                )
                self.send_message(chat_id, success_msg)
                return
            except Exception as e:
                logger.error(f"Error during LMS signin verification: {e}")
                self.send_message(chat_id, "❌ Lexyta server connection error. Kripya apna <b>Email dobara bhejein</b>:")
                self.states[chat_id] = STATE_WAITING_EMAIL
                return

        elif current_state == STATE_WAITING_GEMINI:
            gemini_key = text.strip()
            if gemini_key.lower() == "default" or not gemini_key:
                gemini_key = DEFAULT_GEMINI_KEY

            self.drafts[chat_id]["gemini_api_key"] = gemini_key
            self.states[chat_id] = STATE_WAITING_SEMESTER

            self.send_message(chat_id, "🔑 Gemini API Key configured!\n\n🔹 <b>Step 4/4:</b> Apna <b>Semester Filter</b> batayein:\n<i>(Type karein <code>auto</code> taaki system automatically aapka current semester detect kare, e.g. BCA3, BCA4)</i>")
            return

        elif current_state == STATE_WAITING_SEMESTER:
            semester = text.strip().lower() or "auto"
            self.drafts[chat_id]["semester_filter"] = semester

            # Commit registration to persistent store!
            self.user_manager.register_or_update_user(chat_id, self.drafts[chat_id])
            self.states[chat_id] = STATE_IDLE
            self.drafts.pop(chat_id, None)

            final_msg = (
                "🎉 <b>Registration Complete & Active!</b>\n\n"
                "Aapka Lexyta account successfully linked ho chuka hai aur 24/7 background scanner me add kar diya gaya hai.\n\n"
                "⚡ <b>What happens now:</b>\n"
                "• New Quizzes are solved with Gemini AI & submitted automatically\n"
                "• New Assignments are alerted with exact IST due date & time\n"
                "• Released Marks & Results are sent directly to this chat\n\n"
                "Type /status ya /scan try karein!"
            )
            self.send_message(chat_id, final_msg)
            return

    def poll(self):
        """Continuous long-polling loop to receive incoming Telegram messages."""
        logger.info(f"Telegram Bot server started. Listening on bot token: {self.bot_token[:10]}...")
        self.running = True
        offset = None

        while self.running:
            try:
                url = f"{self.base_url}/getUpdates"
                params = {"timeout": 25}
                if offset:
                    params["offset"] = offset

                resp = requests.get(url, params=params, timeout=35)
                if resp.status_code == 200:
                    data = resp.json()
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        if "message" in update:
                            self.handle_message(update["message"])
                elif resp.status_code in [401, 404]:
                    logger.error(f"Invalid Telegram bot token: {resp.text}")
                    time.sleep(10)
                else:
                    time.sleep(2)
            except Exception as e:
                # Catch network hiccups cleanly
                time.sleep(3)
