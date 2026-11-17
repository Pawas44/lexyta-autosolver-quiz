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
from src.client.lexyta_api import LexytaAPIClient
from src.core.config import DEFAULT_GEMINI_KEY
from src.engine.scanner import detect_active_classes, is_overdue
from src.notifiers.dispatcher import format_datetime_ist
from src.solvers.gemini_solver import GeminiQuizSolver
from src.notifiers.telegram import format_quiz_progress_msg, format_quiz_submitted_msg

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

    def register_telegram_menu_commands(self):
        """Registers bot commands with Telegram so they appear in the UI Menu button."""
        url = f"{self.base_url}/setMyCommands"
        commands = [
            {"command": "quiz", "description": "Check pending quizzes (kitne rehte hain)"},
            {"command": "solve", "description": "Solve pending quizzes with AI now"},
            {"command": "assignments", "description": "Check open assignments (jo de sakte hain)"},
            {"command": "marks", "description": "View released marks & results"},
            {"command": "status", "description": "View account & 24/7 monitor status"},
            {"command": "scan", "description": "Run instant LMS scan"},
            {"command": "help", "description": "Show all available commands"}
        ]
        try:
            requests.post(url, json={"commands": commands}, timeout=10)
            logger.info("Telegram UI menu commands registered successfully.")
        except Exception as e:
            logger.warning(f"Failed to register Telegram menu commands: {e}")

    def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML") -> bool:
        """Sends message to a Telegram chat safely."""
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
                return True
            
            payload.pop("parse_mode", None)
            payload["text"] = text
            resp2 = requests.post(url, json=payload, timeout=20)
            return resp2.status_code == 200
        except Exception as e:
            logger.error(f"Error sending message to {chat_id}: {e}")
            return False

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

    def edit_message(self, chat_id: int, message_id: int, text: str, parse_mode: str = "HTML") -> bool:
        """Edits an existing message in-place for live real-time progress updates."""
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
            resp = requests.post(url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Could not edit message {message_id}: {e}")
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

            elif cmd in ["/marks", "/grades", "/results"]:
                self.handle_marks(chat_id)
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
                    "ℹ️ <b>Lexyta LMS Bot - Commands Guide</b>\n\n"
                    "• /quiz - Check karein kitne quiz rehte hain jo attempt kar sakte hain\n"
                    "• /solve - Pending quizzes ko abhi Gemini AI se solve & submit karein\n"
                    "• /assignments - Jo assignments open hain aur abhi submit kar sakte hain\n"
                    "• /marks - Released exam/quiz scores & results dekhein\n"
                    "• /status - 24/7 background monitor status dekhein\n"
                    "• /scan - Manual full scan pass run karein\n"
                    "• /relink - Email ya password change karein\n"
                    "• /pause - Auto-alerts pause karein\n"
                    "• /resume - Auto-alerts resume karein\n"
                    "• /unlink - Account disconnect karein"
                )
                self.send_message(chat_id, help_msg)
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
                        if item.get("type") == "QUIZ":
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
                        if item.get("type") == "QUIZ":
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
                            if prog_msg_id:
                                self.edit_message(
                                    chat_id,
                                    prog_msg_id,
                                    format_quiz_progress_msg(class_name, item_name, 0, total_q, f"Found {total_q} questions. Gemini AI reasoning engine active...")
                                )

                            def on_progress(completed: int, total: int, step_desc: str):
                                if prog_msg_id:
                                    self.edit_message(
                                        chat_id,
                                        prog_msg_id,
                                        format_quiz_progress_msg(class_name, item_name, completed, total, step_desc)
                                    )

                            answers = solver.solve_quiz(sections, on_progress=on_progress)
                            if answers:
                                if prog_msg_id:
                                    self.edit_message(
                                        chat_id,
                                        prog_msg_id,
                                        format_quiz_progress_msg(class_name, item_name, len(answers), total_q, "Submitting answers to LMS...")
                                    )

                                if client.submit_quiz_answers(class_id, item_id, answers):
                                    elapsed = time.time() - t_start
                                    self.user_manager.mark_quiz_solved(chat_id, item_id)
                                    solved_count += 1
                                    final_msg = format_quiz_submitted_msg(class_name, item_name, len(answers), total_q, elapsed)
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
                elif resp.status_code in [401, 404]:
                    logger.error(f"Invalid Telegram bot token: {resp.text}")
                    time.sleep(10)
                else:
                    time.sleep(2)
            except Exception as e:
                # Catch network hiccups cleanly
                time.sleep(3)
