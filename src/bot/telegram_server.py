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
from typing import Dict, Any, Optional, List

from src.core.user_manager import UserManager
from src.core.access_control import AccessController
from src.client.lexyta_api import LexytaAPIClient
from src.core.config import DEFAULT_GEMINI_KEY
from src.engine.scanner import detect_active_classes, is_overdue
from src.notifiers.dispatcher import format_datetime_ist
from src.solvers.gemini_solver import GeminiQuizSolver
from src.solvers.human_pacer import calculate_target_duration_seconds, wait_with_human_pacing
from src.notifiers.telegram import format_quiz_progress_msg, format_quiz_submitted_msg

logger = logging.getLogger("TelegramServer")

MASTER_BOT_TOKEN = os.getenv("MASTER_BOT_TOKEN", "")

# Conversation State Enums
STATE_IDLE = "IDLE"
STATE_WAITING_EMAIL = "WAITING_EMAIL"
STATE_WAITING_PASSWORD = "WAITING_PASSWORD"
STATE_WAITING_GEMINI = "WAITING_GEMINI"
STATE_WAITING_SEMESTER = "WAITING_SEMESTER"

def format_file_size(size_bytes: int) -> str:
    """Formats raw byte count into human-readable B, KB, MB."""
    if not size_bytes or size_bytes <= 0:
        return "Unknown size"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

class TelegramServer:
    def __init__(self, bot_token: str = None, user_manager: UserManager = None, access_controller: AccessController = None):
        self.bot_token = (bot_token or os.getenv("MASTER_BOT_TOKEN") or MASTER_BOT_TOKEN).strip()
        self.user_manager = user_manager or UserManager()
        self.access_controller = access_controller or AccessController()
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        self.states: Dict[int, str] = {}
        self.drafts: Dict[int, Dict[str, Any]] = {}
        self.user_materials_cache: Dict[int, Dict[str, Any]] = {}
        self.running = False
        self.on_demand_scanner = None  # Injected multi-scanner callback

    def register_telegram_menu_commands(self):
        """Registers bot commands with Telegram so they appear in the UI Menu button."""
        url = f"{self.base_url}/setMyCommands"
        commands = [
            {"command": "status", "description": "View account status & toggle controls"},
            {"command": "stop", "description": "🛑 Stop/Pause 24/7 background bot"},
            {"command": "resume", "description": "▶️ Resume 24/7 background bot"},
            {"command": "autosolve", "description": "⚡ Toggle Auto-Solve (ON/OFF)"},
            {"command": "quiz", "description": "Check pending quizzes (kitne rehte hain)"},
            {"command": "solve", "description": "Solve pending quizzes with AI now"},
            {"command": "assignments", "description": "Check open assignments (jo de sakte hain)"},
            {"command": "notes", "description": "Download lecture notes, PPTs & outlines"},
            {"command": "marks", "description": "View released marks & results"},
            {"command": "scan", "description": "Run instant LMS scan"},
            {"command": "help", "description": "Show all available commands"}
        ]
        try:
            requests.post(url, json={"commands": commands}, timeout=10)
            logger.info("Telegram UI menu commands registered successfully.")
        except Exception as e:
            logger.warning(f"Failed to register Telegram menu commands: {e}")

    def send_document(self, chat_id: int, file_bytes: bytes, filename: str, caption: str = "") -> bool:
        """Sends a document or presentation directly to the user's Telegram chat."""
        try:
            url = f"{self.base_url}/sendDocument"
            files = {
                "document": (filename, file_bytes)
            }
            data = {
                "chat_id": chat_id,
                "caption": caption[:1024] if caption else "",
                "parse_mode": "HTML"
            }
            resp = requests.post(url, data=data, files=files, timeout=60)
            if resp.status_code == 200:
                return True
            # Retry without parse_mode if HTML tags were unescaped
            data.pop("parse_mode", None)
            resp2 = requests.post(url, data=data, files=files, timeout=60)
            return resp2.status_code == 200
        except Exception as e:
            logger.error(f"Error sending document {filename} to {chat_id}: {e}")
            return False

    def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML", reply_markup: Optional[Dict[str, Any]] = None) -> bool:
        """Sends message to a Telegram chat safely, supporting custom inline/reply keyboards."""
        try:
            url = f"{self.base_url}/sendMessage"
            escaped_text = text
            if parse_mode == "HTML":
                escaped_text = re.sub(r'\*([^*]+)\*', r'<b>\1</b>', text)

            payload = {
                "chat_id": chat_id,
                "text": escaped_text,
                "parse_mode": parse_mode
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup

            resp = requests.post(url, json=payload, timeout=20)
            if resp.status_code == 200:
                return True
            
            payload.pop("parse_mode", None)
            payload["text"] = text
            resp2 = requests.post(url, json=payload, timeout=20)
            return resp2.status_code == 200
        except Exception as e:
            logger.error(f"Error sending message to {chat_id}: {e}")
            return False

    def _get_control_keyboard(self, chat_id: int) -> Dict[str, Any]:
        """Generates an interactive Inline Keyboard with 1-tap Stop/Resume and Auto-Solve controls."""
        user = self.user_manager.get_user(chat_id) or {}
        is_active = user.get("is_active", True)
        auto_solve = user.get("auto_solve", True)

        row1 = []
        if is_active:
            row1.append({"text": "🛑 Stop 24/7 Bot", "callback_data": "btn_stop"})
        else:
            row1.append({"text": "▶️ Resume 24/7 Bot", "callback_data": "btn_resume"})

        if auto_solve:
            row1.append({"text": "⚡ Auto-Solve: ON", "callback_data": "btn_autosolve_off"})
        else:
            row1.append({"text": "⏸️ Auto-Solve: OFF", "callback_data": "btn_autosolve_on"})

        row2 = [
            {"text": "🔍 Scan Now", "callback_data": "btn_scan"},
            {"text": "📝 View Quizzes", "callback_data": "btn_quizzes"}
        ]

        return {"inline_keyboard": [row1, row2]}

    def send_message_get_id(self, chat_id: int, text: str, parse_mode: str = "HTML") -> Optional[int]:
        """Sends message and returns message_id for live progress bar editing."""
        try:
            url = f"{self.base_url}/sendMessage"
            escaped_text = text
            if parse_mode == "HTML":
                escaped_text = re.sub(r'\*([^*]+)\*', r'<b>\1</b>', text)

            payload = {
                "chat_id": chat_id,
                "text": escaped_text,
                "parse_mode": parse_mode
            }
            resp = requests.post(url, json=payload, timeout=20)
            if resp.status_code == 200:
                return resp.json().get("result", {}).get("message_id")
            return None
        except Exception as e:
            logger.error(f"Error sending message (get_id) to {chat_id}: {e}")
            return None

    def edit_message(self, chat_id: int, message_id: int, text: str, parse_mode: str = "HTML", reply_markup: Optional[Dict[str, Any]] = None) -> bool:
        """Edits an existing message in-place for live real-time progress updates or keyboard changes."""
        try:
            url = f"{self.base_url}/editMessageText"
            escaped_text = text
            if parse_mode == "HTML":
                escaped_text = re.sub(r'\*([^*]+)\*', r'<b>\1</b>', text)

            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": escaped_text,
                "parse_mode": parse_mode
            }
            if reply_markup is not None:
                payload["reply_markup"] = reply_markup
            resp = requests.post(url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Could not edit message {message_id}: {e}")
            return False

    def answer_callback_query(self, callback_query_id: str, text: Optional[str] = None, show_alert: bool = False) -> bool:
        """Acknowledges a callback query from an inline keyboard to dismiss the loading spinner."""
        try:
            url = f"{self.base_url}/answerCallbackQuery"
            payload = {"callback_query_id": callback_query_id}
            if text:
                payload["text"] = text
                payload["show_alert"] = show_alert
            resp = requests.post(url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Error answering callback query {callback_query_id}: {e}")
            return False

    def handle_callback_query(self, query: Dict[str, Any]):
        """Handles interactive inline button clicks (Stop, Resume, Auto-solve, Scan, Quizzes)."""
        query_id = query.get("id")
        data = query.get("data", "")
        message = query.get("message", {})
        chat = message.get("chat", {})
        chat_id = chat.get("id") or query.get("from", {}).get("id")
        msg_id = message.get("message_id")

        if not chat_id:
            if query_id:
                self.answer_callback_query(query_id)
            return

        if not self.access_controller.is_allowed(chat_id):
            if query_id:
                self.answer_callback_query(query_id, "🔒 Whitelist required", show_alert=True)
            return

        user = self.user_manager.get_user(chat_id)
        if not user or not user.get("email"):
            if query_id:
                self.answer_callback_query(query_id, "⚠️ Koi account link nahi hai. Type /start", show_alert=True)
            return

        if data == "btn_stop":
            self.user_manager.set_user_active(chat_id, False)
            if query_id:
                self.answer_callback_query(query_id, "🛑 24/7 Bot Stopped!")
            new_text = (
                f"🛑 <b>24/7 Bot Paused / Stopped</b>\n\n"
                f"👤 <b>Student:</b> {user.get('student_name', 'Student')} (<code>{user.get('email')}</code>)\n\n"
                f"⚠️ Ab bot background me kuch bhi scan ya auto-solve nahi karega.\n"
                f"Jab aap chahein tab neeche button dabakar ya <code>/resume</code> se wapas chalu kar sakte hain."
            )
            if msg_id:
                self.edit_message(chat_id, msg_id, new_text, reply_markup=self._get_control_keyboard(chat_id))
            else:
                self.send_message(chat_id, new_text, reply_markup=self._get_control_keyboard(chat_id))

        elif data == "btn_resume":
            self.user_manager.set_user_active(chat_id, True)
            if query_id:
                self.answer_callback_query(query_id, "▶️ 24/7 Bot Resumed!")
            new_text = (
                f"▶️ <b>24/7 Bot Active / Resumed!</b>\n\n"
                f"👤 <b>Student:</b> {user.get('student_name', 'Student')} (<code>{user.get('email')}</code>)\n\n"
                f"✅ Background monitoring active hai. Naye quizzes aur assignments track hote rahenge."
            )
            if msg_id:
                self.edit_message(chat_id, msg_id, new_text, reply_markup=self._get_control_keyboard(chat_id))
            else:
                self.send_message(chat_id, new_text, reply_markup=self._get_control_keyboard(chat_id))

        elif data == "btn_autosolve_off":
            self.user_manager.set_user_autosolve(chat_id, False)
            if query_id:
                self.answer_callback_query(query_id, "⏸️ Auto-Solve Disabled (Notify Only)")
            new_text = (
                f"⏸️ <b>Auto-Solve: OFF (Notification-Only Mode)</b>\n\n"
                f"👤 <b>Student:</b> {user.get('student_name', 'Student')} (<code>{user.get('email')}</code>)\n\n"
                f"📢 Jab bhi naya quiz aayega, bot aapko Telegram par alert bhejega par <b>solve ya submit NAHI karega</b>.\n"
                f"Aap classroom me baithkar mobile/laptop par khud quiz de sakte hain bina kisi background interruption ke."
            )
            if msg_id:
                self.edit_message(chat_id, msg_id, new_text, reply_markup=self._get_control_keyboard(chat_id))
            else:
                self.send_message(chat_id, new_text, reply_markup=self._get_control_keyboard(chat_id))

        elif data == "btn_autosolve_on":
            self.user_manager.set_user_autosolve(chat_id, True)
            if query_id:
                self.answer_callback_query(query_id, "⚡ Auto-Solve Enabled (Full Auto)")
            new_text = (
                f"⚡ <b>Auto-Solve: ON (Full Auto Mode)</b>\n\n"
                f"👤 <b>Student:</b> {user.get('student_name', 'Student')} (<code>{user.get('email')}</code>)\n\n"
                f"🤖 Bot 24/7 pending quizzes ko detect karke Gemini AI se automatically solve aur submit karega."
            )
            if msg_id:
                self.edit_message(chat_id, msg_id, new_text, reply_markup=self._get_control_keyboard(chat_id))
            else:
                self.send_message(chat_id, new_text, reply_markup=self._get_control_keyboard(chat_id))

        elif data == "btn_scan":
            if query_id:
                self.answer_callback_query(query_id, "🔍 Scanning LMS...")
            self.send_message(chat_id, "🔍 <i>LMS scan shuru ho raha hai... Please wait...</i>")
            if self.on_demand_scanner:
                res = self.on_demand_scanner(chat_id)
                self.send_message(
                    chat_id,
                    f"✅ Scan Complete!\nQuizzes: {res.get('quizzes', 0)}\nAssignments: {res.get('assignments', 0)}",
                    reply_markup=self._get_control_keyboard(chat_id)
                )
            else:
                self.send_message(chat_id, "✅ On-demand scan queued.", reply_markup=self._get_control_keyboard(chat_id))

        elif data == "btn_quizzes":
            if query_id:
                self.answer_callback_query(query_id)
            self.handle_quiz(chat_id)

        else:
            if query_id:
                self.answer_callback_query(query_id)

    def handle_message(self, message: Dict[str, Any]):
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        text = (message.get("text") or "").strip()
        from_user = message.get("from", {})

        if not chat_id or not text:
            return

        # -------------------------------------------------------------
        # ACCESS CONTROL / GITHUB WHITELIST CHECK
        # -------------------------------------------------------------
        if text.startswith("/"):
            cmd_check = text.split()[0].lower()
            if cmd_check in ["/id", "/myid", "/chatid"]:
                self.send_message(chat_id, f"🆔 <b>Aapka Telegram Chat ID:</b> <code>{chat_id}</code>\n\nIse admin ko bhejein whitelist mein add karwane ke liye.")
                return

        if not self.access_controller.is_allowed(chat_id):
            logger.warning(f"Unauthorized access attempt by chat_id: {chat_id} (@{from_user.get('username', 'none')})")
            denied_msg = (
                "🔒 <b>Access Restricted / Whitelist Required</b>\n\n"
                "Aapka Telegram Chat ID is bot ki authorized users list mein approved nahi hai.\n\n"
                f"🆔 <b>Aapka Chat ID:</b> <code>{chat_id}</code>\n"
                f"👤 <b>Username:</b> @{from_user.get('username') or 'N/A'}\n\n"
                "📌 <b>Kaise Judhein:</b>\n"
                "Yeh Chat ID admin ko bhejein taaki wo aapko GitHub whitelist (<code>allowed_chats.txt</code>) mein add kar sakein."
            )
            self.send_message(chat_id, denied_msg)
            return

        current_state = self.states.get(chat_id, STATE_IDLE)

        # -------------------------------------------------------------
        # GLOBAL COMMANDS
        # -------------------------------------------------------------
        if text.startswith("/"):
            cmd = text.split()[0].lower()

            if cmd in ["/start", "/setup"]:
                user = self.user_manager.get_user(chat_id)
                if user and user.get("email"):
                    name = user.get("student_name", "Student")
                    prog = user.get("program_name", "Program")
                    welcome_back = (
                        f"👋 <b>Welcome back, {name}!</b>\n\n"
                        f"Aapka Lexyta account successfully linked hai:\n"
                        f"📧 <b>Email:</b> <code>{user.get('email')}</code>\n"
                        f"🎓 <b>Program:</b> {prog}\n"
                        f"🟢 <b>Status:</b> 24/7 Autonomous Monitoring Active (5-min scan)\n\n"
                        f"📋 <b>Aap Ye Commands Use Kar Sakte Hain:</b>\n"
                        f"• /quiz - Check karein kitne quiz rehte hain\n"
                        f"• /solve - Pending quizzes ko abhi AI se solve karein\n"
                        f"• /assignments - Jo assignments open hain aur de sakte hain\n"
                        f"• /notes - Lecture notes, PPTs & practical files download karein\n"
                        f"• /marks - Released marks & results dekhein\n"
                        f"• /status - Account & scanner details dekhein\n"
                        f"• /scan - Instant LMS scan pass run karein\n"
                        f"• /relink - Credentials update ya change karein"
                    )
                    self.send_message(chat_id, welcome_back)
                    return

                # Fresh onboarding
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
                    "📂 Lecture notes, PPTs & practical PDFs on-demand send karega\n"
                    "📊 Quiz/Assignment marks aane par result bhejega\n\n"
                    "Chaliye aapka account link karte hain!\n\n"
                    "🔹 <b>Step 1/4:</b> Apna <b>Lexyta LMS Email</b> bhejein:"
                )
                self.send_message(chat_id, welcome_msg)
                return

            elif cmd == "/relink":
                self.states[chat_id] = STATE_WAITING_EMAIL
                self.drafts[chat_id] = {
                    "chat_id": chat_id,
                    "username": from_user.get("username", ""),
                    "first_name": from_user.get("first_name", "")
                }
                self.send_message(chat_id, "🔄 <b>Account Re-linking:</b>\n\n🔹 <b>Step 1/4:</b> Apna <b>Lexyta LMS Email</b> bhejein:")
                return

            elif cmd in ["/quiz", "/quizzes"]:
                self.handle_quiz(chat_id)
                return

            elif cmd in ["/solve", "/quizsolve"]:
                self.handle_solve(chat_id)
                return

            elif cmd in ["/assignments", "/assignment", "/pending"]:
                self.handle_assignments(chat_id)
                return

            elif cmd in ["/notes", "/materials", "/material", "/ppts", "/lecture"] or cmd.startswith("/notes_"):
                self.handle_notes(chat_id, text)
                return

            elif cmd in ["/getfile"] or cmd.startswith("/getfile_"):
                self.handle_getfile(chat_id, text)
                return

            elif cmd == "/getall":
                self.handle_getall(chat_id)
                return

            elif cmd in ["/marks", "/grades", "/results"]:
                self.handle_marks(chat_id)
                return

            elif cmd in ["/status", "/settings", "/control"]:
                user = self.user_manager.get_user(chat_id)
                if not user or not user.get("email"):
                    self.send_message(chat_id, "⚠️ Aapka koi account link nahi hai. Type karein /start apna account connect karne ke liye.")
                    return
                
                status_str = "🟢 Active (Monitoring 24/7)" if user.get("is_active", True) else "🛑 Paused / Stopped"
                auto_solve_str = "⚡ Enabled (Auto-solves quizzes)" if user.get("auto_solve", True) else "⏸️ Disabled (Notification Only)"
                msg = (
                    f"📊 <b>LMS Lexyta Monitoring & Control</b>\n\n"
                    f"👤 <b>Student:</b> {user.get('student_name', 'Student')}\n"
                    f"📧 <b>Email:</b> {user.get('email')}\n"
                    f"🎓 <b>Program:</b> {user.get('program_name')}\n"
                    f"🔄 <b>Semester Filter:</b> {user.get('semester_filter', 'auto')}\n"
                    f"⚡ <b>24/7 Bot:</b> {status_str}\n"
                    f"🤖 <b>Auto-Solve:</b> {auto_solve_str}\n"
                    f"🕒 <b>Last Scan:</b> {user.get('last_scan_utc', 'Pending first scan')}\n"
                    f"🎯 <b>Solved Quizzes:</b> {len(user.get('solved_quizzes', []))}\n"
                    f"📢 <b>Notified Assignments:</b> {len(user.get('notified_assignments', []))}\n\n"
                    f"<i>Neeche diye gaye buttons se bot ko ON/OFF control karein:</i>"
                )
                self.send_message(chat_id, msg, reply_markup=self._get_control_keyboard(chat_id))
                return

            elif cmd == "/scan":
                user = self.user_manager.get_user(chat_id)
                if not user or not user.get("email"):
                    self.send_message(chat_id, "⚠️ Aapka koi account link nahi hai. Type karein /start.")
                    return
                self.send_message(chat_id, "🔍 <i>LMS scan shuru ho raha hai... Please wait...</i>")
                if self.on_demand_scanner:
                    res = self.on_demand_scanner(chat_id)
                    self.send_message(chat_id, f"✅ Scan Complete!\nQuizzes solved: {res.get('quizzes', 0)}\nAssignments alerted: {res.get('assignments', 0)}", reply_markup=self._get_control_keyboard(chat_id))
                else:
                    self.send_message(chat_id, "✅ On-demand scan queued. Background runner will check within a few moments.", reply_markup=self._get_control_keyboard(chat_id))
                return

            elif cmd in ["/stop", "/pause", "/off", "/disable"]:
                if self.user_manager.set_user_active(chat_id, False):
                    self.send_message(
                        chat_id,
                        "🛑 <b>24/7 Bot Stopped / Paused!</b>\n\n"
                        "Ab background runner aapke LMS account ko scan ya solve nahi karega.\n"
                        "Jab resume karna ho, <code>/resume</code> type karein ya neeche button dabayein.",
                        reply_markup=self._get_control_keyboard(chat_id)
                    )
                else:
                    self.send_message(chat_id, "⚠️ Koi account link nahi hai. Type /start")
                return

            elif cmd in ["/resume", "/start_auto", "/on", "/enable"]:
                if self.user_manager.set_user_active(chat_id, True):
                    self.send_message(
                        chat_id,
                        "▶️ <b>24/7 Bot Resumed / Active!</b>\n\n"
                        "System background me 24/7 aapke pending quizzes aur assignments monitor karta rahega.",
                        reply_markup=self._get_control_keyboard(chat_id)
                    )
                else:
                    self.send_message(chat_id, "⚠️ Koi account link nahi hai. Type /start")
                return

            elif cmd in ["/autosolve", "/solvemode"]:
                user = self.user_manager.get_user(chat_id)
                if not user or not user.get("email"):
                    self.send_message(chat_id, "⚠️ Koi account link nahi hai. Type /start")
                    return
                parts = text.split()
                current = user.get("auto_solve", True)
                if len(parts) > 1:
                    arg = parts[1].strip().lower()
                    if arg in ["off", "stop", "disable", "no", "false", "pause"]:
                        new_state = False
                    elif arg in ["on", "start", "enable", "yes", "true", "resume"]:
                        new_state = True
                    else:
                        new_state = not current
                else:
                    new_state = not current
                self.user_manager.set_user_autosolve(chat_id, new_state)
                state_str = "⚡ <b>Enabled</b> (Full Auto: detects & auto-submits)" if new_state else "⏸️ <b>Disabled</b> (Notification Only: won't touch quizzes)"
                self.send_message(
                    chat_id,
                    f"🤖 Auto-Solve status: {state_str}\n\n<i>Toggle karne ke liye buttons ka use karein:</i>",
                    reply_markup=self._get_control_keyboard(chat_id)
                )
                return

            elif cmd == "/unlink" or cmd == "/logout":
                self.user_manager.delete_user(chat_id)
                self.states[chat_id] = STATE_IDLE
                self.send_message(chat_id, "🗑️ Aapka account Lexyta Bot se <b>unlink kar diya gaya hai</b>. Naye account ke liye /start dabayein.")
                return

            elif cmd == "/help":
                help_msg = (
                    "ℹ️ <b>Lexyta LMS Bot - Commands Guide</b>\n\n"
                    "• /status - 24/7 monitor status aur Stop/Resume control buttons dekhein\n"
                    "• /stop - 24/7 bot ko pause/stop karein (exam ke time safe rehne ke liye)\n"
                    "• /resume - 24/7 bot ko wapas active/chalu karein\n"
                    "• /autosolve - Auto-solve toggle karein (ON = AI auto-solve, OFF = notify only)\n"
                    "• /quiz - Check karein kitne quiz rehte hain jo attempt kar sakte hain\n"
                    "• /solve - Pending quizzes ko abhi Gemini AI se solve & submit karein\n"
                    "• /assignments - Jo assignments open hain aur abhi submit kar sakte hain\n"
                    "• /notes - Lecture notes, PPTs & outlines download karein\n"
                    "• /marks - Released exam/quiz scores & results dekhein\n"
                    "• /scan - Manual full scan pass run karein\n"
                    "• /relink - Email ya password change karein\n"
                    "• /unlink - Account disconnect karein"
                )
                self.send_message(chat_id, help_msg, reply_markup=self._get_control_keyboard(chat_id))
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
            user_data = self.drafts[chat_id]
            self.user_manager.register_or_update_user(chat_id, user_data)
            self.states[chat_id] = STATE_IDLE
            self.drafts.pop(chat_id, None)

            # Silently pre-seed past grades and completed items so new user isn't spammed with old history
            try:
                c_seed = LexytaAPIClient(user_data["email"], user_data["password"])
                if c_seed.signin():
                    progs = c_seed.get_enrolled_programs() or []
                    for prg in progs:
                        clss = c_seed.get_program_classes(prg["id"]) or []
                        act_cls = detect_active_classes(clss, semester)
                        for c_item in act_cls:
                            itms = c_seed.get_class_assignments(c_item["id"]) or []
                            for it in itms:
                                iid = it["id"]
                                lat = it.get("latest_attempt")
                                if lat:
                                    if lat.get("grade"):
                                        self.user_manager.mark_grade_notified(chat_id, iid)
                                    if lat.get("status") in ["COMPLETED", "SUBMITTED", "GRADED"]:
                                        self.user_manager.mark_assignment_notified(chat_id, iid)
                    self.user_manager.flush_cloud_state()
            except Exception as e:
                logger.warning(f"Onboarding pre-seed failed for {chat_id}: {e}")

            final_msg = (
                "🎉 <b>Registration Complete & Active!</b>\n\n"
                "Aapka Lexyta account successfully linked ho chuka hai aur 24/7 background scanner me add kar diya gaya hai.\n\n"
                "⚡ <b>What happens now:</b>\n"
                "• New Quizzes are solved with Gemini AI & submitted automatically\n"
                "• New Assignments are alerted with exact IST due date & time\n"
                "• Released Marks & Results are sent directly to this chat\n"
                "• /notes se kisi bhi subject ke notes & PPTs download karein\n\n"
                "Type /status ya /scan try karein!"
            )
            self.send_message(chat_id, final_msg)
            return

    def handle_quiz(self, chat_id: int):
        """Scans and lists pending vs completed quizzes for the student."""
        user = self.user_manager.get_user(chat_id)
        if not user or not user.get("email"):
            self.send_message(chat_id, "⚠️ Pehle apna LMS account connect karein: /start")
            return

        self.send_message(chat_id, "🔍 <i>Checking Lexyta LMS for quizzes...</i>")

        try:
            client = LexytaAPIClient(user["email"], user["password"])
            if not client.signin():
                self.send_message(chat_id, "❌ LMS Login failed. Please type /relink to re-enter your password.")
                return

            sem_filter = user.get("semester_filter", "auto")
            programs = client.get_enrolled_programs() or []
            pending_quizzes = []
            completed_quizzes = []

            for prog in programs:
                classes = client.get_program_classes(prog["id"]) or []
                active_classes = detect_active_classes(classes, sem_filter)
                for cls in active_classes:
                    items = client.get_class_assignments(cls["id"]) or []
                    for item in items:
                        is_quiz = (item.get("type") in ["QUIZ", "EXAM", "TEST", "ASSESSMENT", "ONLINE_QUIZ"]) or \
                                  (any(w in item.get("name", "").lower() for w in ["quiz", "grand"]) and item.get("type") not in ["DOCUMENT", "HOMEWORK"])
                        if is_quiz:
                            latest = item.get("latest_attempt")
                            status = latest.get("status") if latest else "NOT_ATTEMPTED"
                            due = item.get("due_date")
                            overdue = is_overdue(due)

                            q_info = {
                                "class_id": cls["id"],
                                "class_name": cls.get("name", "Unknown Subject"),
                                "item_id": item["id"],
                                "name": item.get("name", "Quiz"),
                                "due_date": due,
                                "status": status,
                                "max_score": item.get("max_score")
                            }

                            if status in ["COMPLETED", "GRADED"] or self.user_manager.is_quiz_solved(chat_id, item["id"]):
                                completed_quizzes.append(q_info)
                            elif not overdue:
                                pending_quizzes.append(q_info)

            if not pending_quizzes:
                msg = "🎉 <b>Sabhi Quizzes Complete Hain!</b>\n\nAbhi koi bhi pending quiz nahi hai jo attempt karna baaki ho."
                if completed_quizzes:
                    msg += f"\n\n✅ <b>Completed / Solved Quizzes:</b> {len(completed_quizzes)}"
                self.send_message(chat_id, msg)
                return

            msg = f"📝 <b>Aapke {len(pending_quizzes)} Quiz Rehte Hain (Pending):</b>\n\n"
            for idx, q in enumerate(pending_quizzes, 1):
                due_str = format_datetime_ist(q["due_date"])
                msg += (
                    f"<b>{idx}. {q['name']}</b>\n"
                    f"   📚 Subject: <b>{q['class_name']}</b>\n"
                    f"   ⏰ Deadline: {due_str}\n"
                    f"   🎯 Max Marks: {q['max_score'] or 'N/A'}\n"
                    f"   ⚡ Status: ⏳ Pending Submission\n\n"
                )

            msg += "👉 <b>AI se abhi solve karne ke liye type karein:</b> /solve"
            self.send_message(chat_id, msg)

        except Exception as e:
            logger.error(f"Error handling /quiz: {e}", exc_info=True)
            self.send_message(chat_id, f"⚠️ LMS check karte waqt error aaya: {e}")

    def handle_solve(self, chat_id: int):
        """Immediately solves all pending quizzes with live progress bar in Telegram."""
        user = self.user_manager.get_user(chat_id)
        if not user or not user.get("email"):
            self.send_message(chat_id, "⚠️ Pehle apna account link karein: /start")
            return

        self.send_message(chat_id, "⚡ <i>Starting on-demand AI quiz solver...</i>")

        try:
            client = LexytaAPIClient(user["email"], user["password"])
            if not client.signin():
                self.send_message(chat_id, "❌ LMS Login failed. Please type /relink.")
                return

            sem_filter = user.get("semester_filter", "auto")
            gemini_key = user.get("gemini_api_key") or DEFAULT_GEMINI_KEY
            solver = GeminiQuizSolver(gemini_key)
            programs = client.get_enrolled_programs() or []

            solved_count = 0

            for prog in programs:
                classes = client.get_program_classes(prog["id"]) or []
                active_classes = detect_active_classes(classes, sem_filter)
                for cls in active_classes:
                    class_id = cls["id"]
                    class_name = cls.get("name", "Unknown Subject")
                    items = client.get_class_assignments(class_id) or []

                    for item in items:
                        is_quiz = (item.get("type") in ["QUIZ", "EXAM", "TEST", "ASSESSMENT", "ONLINE_QUIZ"]) or \
                                  (any(w in item.get("name", "").lower() for w in ["quiz", "grand"]) and item.get("type") not in ["DOCUMENT", "HOMEWORK"])
                        if is_quiz:
                            item_id = item["id"]
                            item_name = item.get("name", "Quiz")
                            latest = item.get("latest_attempt")
                            status = latest.get("status") if latest else "NOT_ATTEMPTED"
                            due = item.get("due_date")

                            if status in ["COMPLETED", "GRADED"] or self.user_manager.is_quiz_solved(chat_id, item_id):
                                continue
                            if is_overdue(due):
                                continue

                            # Live Progress Tracker
                            t_start = time.time()
                            init_text = (
                                f"🚀 <b>LMS Quiz Started!</b>\n\n"
                                f"📚 <b>Subject:</b> {class_name}\n"
                                f"📝 <b>Quiz:</b> {item_name}\n"
                                f"⏳ <b>Status:</b> Initializing attempt and downloading questions..."
                            )
                            prog_msg_id = self.send_message_get_id(chat_id, init_text)

                            if status == "NOT_ATTEMPTED":
                                client.start_quiz_attempt(class_id, item_id)

                            sections = client.get_quiz_questions(class_id, item_id)
                            if not sections:
                                if prog_msg_id:
                                    self.edit_message(chat_id, prog_msg_id, f"⚠️ Questions load nahi ho paye for <b>{item_name}</b>.")
                                continue

                            total_q = sum(len(s.get("questions", [])) for s in sections)
                            student_name = user.get("student_name", "Student")
                            if prog_msg_id:
                                self.edit_message(
                                    chat_id,
                                    prog_msg_id,
                                    format_quiz_progress_msg(class_name, item_name, 0, total_q, f"Found {total_q} questions. Gemini AI reasoning engine active...", student_name=student_name)
                                )

                            def on_progress(completed: int, total: int, step_desc: str):
                                if prog_msg_id:
                                    self.edit_message(
                                        chat_id,
                                        prog_msg_id,
                                        format_quiz_progress_msg(class_name, item_name, completed, total, step_desc, student_name=student_name)
                                    )

                            answers = solver.solve_quiz(sections, on_progress=on_progress)
                            if answers:
                                # Realistic human pacing (e.g. ~35s per question with human variance)
                                time_limit = item.get("time_limit")
                                target_dur = calculate_target_duration_seconds(time_limit, total_q, due_date_str=due)

                                def on_pace_tick(elapsed_sec: float, remaining_sec: float, status_str: str):
                                    if prog_msg_id:
                                        self.edit_message(
                                            chat_id,
                                            prog_msg_id,
                                            format_quiz_progress_msg(class_name, item_name, len(answers), total_q, status_str, student_name=student_name)
                                        )

                                wait_with_human_pacing(t_start, target_dur, on_tick=on_pace_tick, tick_interval=15.0, total_questions=total_q)

                                if client.submit_quiz_answers(class_id, item_id, answers):
                                    elapsed = time.time() - t_start
                                    self.user_manager.mark_quiz_solved(chat_id, item_id)
                                    self.user_manager.flush_cloud_state()
                                    solved_count += 1
                                    final_msg = format_quiz_submitted_msg(class_name, item_name, len(answers), total_q, elapsed, student_name=student_name)
                                    if prog_msg_id:
                                        self.edit_message(chat_id, prog_msg_id, final_msg)
                                    else:
                                        self.send_message(chat_id, final_msg)
                                else:
                                    if prog_msg_id:
                                        self.edit_message(chat_id, prog_msg_id, f"❌ Submission failed for <b>{item_name}</b>.")

            if solved_count == 0:
                self.send_message(chat_id, "ℹ️ Abhi koi naya pending quiz solve karne ke liye nahi mila. (/quiz se status dekhein)")
            else:
                self.send_message(chat_id, f"✅ Total <b>{solved_count} quiz(zes) successfully solve & submit</b> ho gaye!")

        except Exception as e:
            logger.error(f"Error handling /solve: {e}", exc_info=True)
            self.send_message(chat_id, f"⚠️ Solve karte waqt error: {e}")

    def handle_assignments(self, chat_id: int):
        """Shows open assignments that haven't been submitted and deadline has not passed."""
        user = self.user_manager.get_user(chat_id)
        if not user or not user.get("email"):
            self.send_message(chat_id, "⚠️ Pehle apna account connect karein: /start")
            return

        self.send_message(chat_id, "📋 <i>Checking Lexyta LMS for open assignments...</i>")

        try:
            client = LexytaAPIClient(user["email"], user["password"])
            if not client.signin():
                self.send_message(chat_id, "❌ LMS Login failed. Please type /relink.")
                return

            sem_filter = user.get("semester_filter", "auto")
            programs = client.get_enrolled_programs() or []
            pending_asgns = []

            for prog in programs:
                classes = client.get_program_classes(prog["id"]) or []
                active_classes = detect_active_classes(classes, sem_filter)
                for cls in active_classes:
                    items = client.get_class_assignments(cls["id"]) or []
                    for item in items:
                        if item.get("type") != "QUIZ":
                            latest = item.get("latest_attempt")
                            status = latest.get("status") if latest else "NOT_ATTEMPTED"
                            due = item.get("due_date")

                            # Only active, unexpired, unsubmitted assignments!
                            if status not in ["COMPLETED", "GRADED", "SUBMITTED"] and not is_overdue(due):
                                pending_asgns.append({
                                    "class_name": cls.get("name", "Unknown Subject"),
                                    "name": item.get("name", "Assignment"),
                                    "due_date": due,
                                    "max_score": item.get("max_score")
                                })

            if not pending_asgns:
                self.send_message(chat_id, "🎉 <b>Koi Pending Assignment Nahi Hai!</b>\n\nSabhi open assignments submit ho chuke hain ya deadline over ho chuki hai.")
                return

            msg = f"📋 <b>Open Assignments (Jo Abhi De Sakte Hain):</b>\n\n"
            for idx, a in enumerate(pending_asgns, 1):
                due_str = format_datetime_ist(a["due_date"])
                msg += (
                    f"<b>{idx}. {a['name']}</b>\n"
                    f"   📚 Subject: <b>{a['class_name']}</b>\n"
                    f"   ⏰ Due Date: <b>{due_str}</b>\n"
                    f"   🎯 Max Marks: {a['max_score'] or 'N/A'}\n"
                    f"   ⚡ Status: ⏳ Submission Open (Not Submitted Yet)\n\n"
                )

            msg += "🌐 <i>Portal par submit karne ke liye: https://lms.lexyta.com</i>"
            self.send_message(chat_id, msg)

        except Exception as e:
            logger.error(f"Error in /assignments: {e}", exc_info=True)
            self.send_message(chat_id, f"⚠️ Error fetching assignments: {e}")

    def handle_marks(self, chat_id: int):
        """Shows released grades and scores across all active subjects."""
        user = self.user_manager.get_user(chat_id)
        if not user or not user.get("email"):
            self.send_message(chat_id, "⚠️ Pehle apna account connect karein: /start")
            return

        self.send_message(chat_id, "📊 <i>Fetching released marks from Lexyta LMS...</i>")

        try:
            client = LexytaAPIClient(user["email"], user["password"])
            if not client.signin():
                self.send_message(chat_id, "❌ LMS Login failed. Please type /relink.")
                return

            sem_filter = user.get("semester_filter", "auto")
            programs = client.get_enrolled_programs() or []
            grades = []

            for prog in programs:
                classes = client.get_program_classes(prog["id"]) or []
                active_classes = detect_active_classes(classes, sem_filter)
                for cls in active_classes:
                    items = client.get_class_assignments(cls["id"]) or []
                    for item in items:
                        latest = item.get("latest_attempt")
                        if latest:
                            grade_obj = latest.get("grade")
                            if grade_obj and grade_obj.get("released"):
                                g_val = grade_obj.get("grade")
                                if g_val is not None:
                                    grader_name = ""
                                    graded_by = grade_obj.get("graded_by")
                                    if graded_by:
                                        grader_name = f"{graded_by.get('first_name', '')} {graded_by.get('last_name', '')}".strip()

                                    grades.append({
                                        "class_name": cls.get("name", "Unknown Subject"),
                                        "name": item.get("name", "Item"),
                                        "grade": g_val,
                                        "max_score": item.get("max_score"),
                                        "type": item.get("type", "ASSIGNMENT"),
                                        "graded_by": grader_name
                                    })

            if not grades:
                self.send_message(chat_id, "ℹ️ Abhi tak koi naye marks / results release nahi hue hain.")
                return

            msg = f"📊 <b>Released Marks & Results ({len(grades)} Items):</b>\n\n"
            for idx, g in enumerate(grades, 1):
                max_s = g["max_score"]
                pct = f" ({(g['grade']/max_s)*100:.1f}%)" if max_s else ""
                icon = "📝 Quiz" if g["type"] == "QUIZ" else "📄 Assignment"
                eval_str = f" | 👨‍🏫 {g['graded_by']}" if g['graded_by'] else ""
                msg += (
                    f"<b>{idx}. {g['name']}</b> ({icon})\n"
                    f"   📚 Subject: {g['class_name']}\n"
                    f"   🎯 Score: <b>{g['grade']} / {max_s or 'N/A'}</b>{pct}{eval_str}\n\n"
                )
            msg += "🌐 <i>Check full results on Lexyta LMS</i>"
            self.send_message(chat_id, msg)

        except Exception as e:
            logger.error(f"Error in /marks: {e}", exc_info=True)
            self.send_message(chat_id, f"⚠️ Error fetching marks: {e}")

    def handle_notes(self, chat_id: int, command_text: str = "/notes"):
        """Lists active subjects or fetches lecture notes/PPTs/outlines for a selected subject."""
        user = self.user_manager.get_user(chat_id)
        if not user or not user.get("email"):
            self.send_message(chat_id, "⚠️ Pehle apna LMS account connect karein: /start")
            return

        parts = command_text.strip().split(maxsplit=1)
        sub_cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        # Check for /notes_1 or /notes 1
        query = ""
        if "_" in sub_cmd:
            query = sub_cmd.split("_", 1)[1]
        elif arg:
            query = arg

        try:
            client = LexytaAPIClient(user["email"], user["password"])
            if not client.signin():
                self.send_message(chat_id, "❌ LMS Login failed. Please type /relink.")
                return

            sem_filter = user.get("semester_filter", "auto")
            programs = client.get_enrolled_programs() or []
            if not programs:
                self.send_message(chat_id, "⚠️ Koi enrolled program nahi mila.")
                return

            # Discover active classes dynamically across programs
            active_classes = []
            for prog in programs:
                classes = client.get_program_classes(prog["id"]) or []
                active_classes.extend(detect_active_classes(classes, sem_filter))

            if not active_classes:
                self.send_message(chat_id, "⚠️ Koi active subjects/classes nahi mili.")
                return

            # Cache the active classes for index lookup
            if chat_id not in self.user_materials_cache:
                self.user_materials_cache[chat_id] = {}
            self.user_materials_cache[chat_id]["classes"] = active_classes

            # Resolve selected subject if query provided
            selected_class = None
            if query:
                if query.isdigit():
                    idx = int(query) - 1
                    if 0 <= idx < len(active_classes):
                        selected_class = active_classes[idx]
                else:
                    matches = [c for c in active_classes if query.lower() in c.get("name", "").lower()]
                    if len(matches) == 1:
                        selected_class = matches[0]
                    elif len(matches) > 1:
                        active_classes = matches

            # If no subject selected yet, show list of subjects
            if not selected_class:
                prog_name = user.get("program_name") or programs[0].get("name", "Academic Program")
                msg = (
                    f"📂 <b>LMS Lecture Notes & Study Materials</b>\n"
                    f"🎓 Program: <b>{prog_name}</b>\n\n"
                    f"Kripya subject select karein jiske notes, PPTs ya practical files download karni hain:\n\n"
                )
                for i, cls in enumerate(active_classes, 1):
                    msg += f"{i}️⃣ <b>{cls.get('name', 'Subject')}</b> (<code>/notes_{i}</code>)\n"

                msg += "\n💡 <i>Kisi bhi subject command par tap karein (e.g. <code>/notes_1</code>) ya type karein: <code>/notes 1</code></i>"
                self.send_message(chat_id, msg)
                return

            # Subject selected! Fetch all materials for this subject
            class_id = selected_class["id"]
            class_name = selected_class.get("name", "Selected Subject")
            course_id = selected_class.get("course", {}).get("id")

            self.send_message(chat_id, f"🔍 <i>Subject <b>{class_name}</b> ke sabhi materials collect kiye ja rahe hain...</i>")

            all_files = []
            seen_file_ids = set()

            # 1. Class Resources (Timetables, Delivery Plans, Course Outlines)
            resources = client.get_class_resources(class_id)
            for r in resources:
                f = r.get("file")
                if f and f.get("id") and f.get("id") not in seen_file_ids:
                    seen_file_ids.add(f["id"])
                    all_files.append({
                        "id": f["id"],
                        "name": f.get("name", "Resource Document"),
                        "size": f.get("size", 0),
                        "type": f.get("type", ""),
                        "category": r.get("type", "CLASS_RESOURCE").replace("_", " ").title(),
                        "url": f.get("url")
                    })

            # 2. Syllabus Topics (PPTs, Lecture notes)
            if course_id:
                topics = client.get_course_topics(course_id)
                for t in topics:
                    t_name = t.get("name", "Lecture Topic")
                    for f in t.get("files", []):
                        if f.get("id") and f.get("id") not in seen_file_ids:
                            seen_file_ids.add(f["id"])
                            all_files.append({
                                "id": f["id"],
                                "name": f.get("name", "Lecture Notes"),
                                "size": f.get("size", 0),
                                "type": f.get("type", ""),
                                "category": f"Topic: {t_name}",
                                "url": None
                            })

            # 3. Assignment / Practical Attachments
            assignments = client.get_class_assignments(class_id)
            for a in assignments:
                asgn_id = a.get("id")
                asgn_name = a.get("name", "Assignment")
                details = client.get_assignment_details(class_id, asgn_id)
                if details:
                    for f in details.get("files", []):
                        if f.get("id") and f.get("id") not in seen_file_ids:
                            seen_file_ids.add(f["id"])
                            all_files.append({
                                "id": f["id"],
                                "name": f.get("name", "Assignment File"),
                                "size": f.get("size", 0),
                                "type": f.get("type", ""),
                                "category": f"Practical: {asgn_name}",
                                "url": None
                            })

            if not all_files:
                self.send_message(
                    chat_id,
                    f"ℹ️ <b>{class_name}</b> me abhi tak koi PPT ya PDF upload nahi kiya gaya hai.\n\n"
                    f"Dusra subject dekhne ke liye: /notes"
                )
                return

            # Store in cache for on-demand downloads
            file_map = {}
            for idx, item in enumerate(all_files, 1):
                file_map[str(idx)] = item
            self.user_materials_cache[chat_id]["files"] = file_map
            self.user_materials_cache[chat_id]["selected_class"] = class_name

            msg = (
                f"📚 <b>Materials for {class_name}:</b>\n"
                f"Total Available Files: <b>{len(all_files)}</b>\n\n"
            )

            for idx, f in enumerate(all_files, 1):
                size_str = format_file_size(f.get("size", 0))
                ext = f.get("name", "").split(".")[-1].lower()
                icon = "📊" if ext in ["ppt", "pptx"] else ("📑" if ext in ["doc", "docx"] else "📄")
                msg += (
                    f"<b>{idx}. {icon} {f['name']}</b> ({size_str})\n"
                    f"   📁 {f['category']}\n"
                    f"   👉 Download: <code>/getfile_{idx}</code>\n\n"
                )

            msg += (
                "-----------------------------------------------\n"
                "📥 <b>File mangwane ke liye:</b> Upar diye kisi bhi <code>/getfile_N</code> par click karein!\n"
                "📦 <b>Sabhi ek sath mangwane ke liye:</b> /getall\n"
                "🔙 <b>Dusra subject dekhne ke liye:</b> /notes"
            )
            self.send_message(chat_id, msg)

        except Exception as e:
            logger.error(f"Error handling /notes: {e}", exc_info=True)
            self.send_message(chat_id, f"⚠️ Notes fetch karte waqt error aaya: {e}")

    def handle_getfile(self, chat_id: int, command_text: str = "/getfile"):
        """Downloads a specific file requested by the student and sends it to Telegram."""
        user = self.user_manager.get_user(chat_id)
        if not user or not user.get("email"):
            self.send_message(chat_id, "⚠️ Pehle apna LMS account connect karein: /start")
            return

        cache = self.user_materials_cache.get(chat_id, {})
        file_map = cache.get("files", {})
        if not file_map:
            self.send_message(chat_id, "⚠️ Pehle subject select karke files list karein: /notes")
            return

        parts = command_text.strip().split(maxsplit=1)
        sub_cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        target_key = ""
        if "_" in sub_cmd:
            target_key = sub_cmd.split("_", 1)[1]
        elif arg:
            target_key = arg

        if not target_key or target_key not in file_map:
            self.send_message(chat_id, "⚠️ File number invalid hai. Type karein <code>/getfile 1</code> ya <code>/getfile_1</code>.")
            return

        file_info = file_map[target_key]
        fname = file_info["name"]
        fid = file_info["id"]
        direct_url = file_info.get("url")
        cls_name = cache.get("selected_class", "Subject")
        size_str = format_file_size(file_info.get("size", 0))

        self.send_message(chat_id, f"⏳ <i>Downloading <b>{fname}</b> ({size_str}) from LMS...</i>")

        try:
            client = LexytaAPIClient(user["email"], user["password"])
            if not client.signin():
                self.send_message(chat_id, "❌ LMS Login failed. Please type /relink.")
                return

            raw_bytes = client.download_file_bytes(direct_url or fid)
            if not raw_bytes:
                self.send_message(chat_id, f"❌ <b>{fname}</b> download nahi ho payi. File LMS par unavailable ho sakti hai.")
                return

            caption = (
                f"📄 <b>{fname}</b>\n"
                f"📚 Subject: <b>{cls_name}</b>\n"
                f"📁 {file_info.get('category', 'Study Material')}\n"
                f"⚡ <i>LMS Lexyta Notes Downloader</i>"
            )

            sent = self.send_document(chat_id, raw_bytes, fname, caption)
            if not sent:
                self.send_message(chat_id, f"⚠️ File download ho gayi lekin Telegram par send nahi ho saki ({size_str}).")
        except Exception as e:
            logger.error(f"Error in handle_getfile: {e}", exc_info=True)
            self.send_message(chat_id, f"⚠️ Download error: {e}")

    def handle_getall(self, chat_id: int):
        """Downloads and forwards all files of the currently selected subject."""
        user = self.user_manager.get_user(chat_id)
        if not user or not user.get("email"):
            self.send_message(chat_id, "⚠️ Pehle apna LMS account connect karein: /start")
            return

        cache = self.user_materials_cache.get(chat_id, {})
        file_map = cache.get("files", {})
        if not file_map:
            self.send_message(chat_id, "⚠️ Pehle subject select karein: /notes")
            return

        cls_name = cache.get("selected_class", "Subject")
        total_files = len(file_map)
        self.send_message(
            chat_id,
            f"📦 <i><b>{cls_name}</b> ki sabhi {total_files} files download karke bhejna shuru kar raha hoon... Please wait...</i>"
        )

        try:
            client = LexytaAPIClient(user["email"], user["password"])
            if not client.signin():
                self.send_message(chat_id, "❌ LMS Login failed. Please type /relink.")
                return

            sent_count = 0
            for idx_str, file_info in file_map.items():
                fname = file_info["name"]
                fid = file_info["id"]
                direct_url = file_info.get("url")

                raw_bytes = client.download_file_bytes(direct_url or fid)
                if raw_bytes:
                    caption = (
                        f"📄 <b>{fname}</b>\n"
                        f"📚 Subject: <b>{cls_name}</b>\n"
                        f"📁 {file_info.get('category', 'Study Material')}\n"
                        f"⚡ <i>File ({idx_str}/{total_files})</i>"
                    )
                    if self.send_document(chat_id, raw_bytes, fname, caption):
                        sent_count += 1
                        time.sleep(1.5)  # Telegram API flood prevention

            self.send_message(chat_id, f"🎉 <b>Complete!</b> {sent_count}/{total_files} files aapke chat me bhej di gayi hain.")
        except Exception as e:
            logger.error(f"Error in handle_getall: {e}", exc_info=True)
            self.send_message(chat_id, f"⚠️ Error: {e}")

    def poll(self):
        """Continuous long-polling loop to receive incoming Telegram messages."""
        logger.info(f"Telegram Bot server started. Listening on bot token: {self.bot_token[:10]}...")
        self.register_telegram_menu_commands()
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
                        elif "callback_query" in update:
                            self.handle_callback_query(update["callback_query"])
                elif resp.status_code in [401, 404]:
                    logger.error(f"Invalid Telegram bot token: {resp.text}")
                    time.sleep(10)
                else:
                    time.sleep(2)
            except Exception as e:
                # Catch network hiccups cleanly
                time.sleep(3)
