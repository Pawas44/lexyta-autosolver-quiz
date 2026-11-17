"""
Multi-Tenant LMS Scanner
Iterates over all registered students, solves quizzes, alerts on assignments and marks.
"""

import logging
from typing import Dict, Any, Optional

from src.core.user_manager import UserManager
from src.client.lexyta_api import LexytaAPIClient
from src.solvers.gemini_solver import GeminiQuizSolver
from src.notifiers.telegram import TelegramNotifier
from src.notifiers.dispatcher import format_datetime_ist
from src.engine.scanner import is_overdue, detect_active_classes
from src.core.config import DEFAULT_GEMINI_KEY

logger = logging.getLogger("MultiScanner")

class MultiScanner:
    def __init__(self, user_manager: UserManager, bot_token: str):
        self.user_manager = user_manager
        self.bot_token = bot_token

    def scan_user(self, user: Dict[str, Any], dry_run: bool = False) -> Dict[str, int]:
        """Scans LMS for a single student."""
        chat_id = user["chat_id"]
        email = user["email"]
        password = user["password"]
        gemini_key = user.get("gemini_api_key") or DEFAULT_GEMINI_KEY
        sem_filter = user.get("semester_filter", "auto")
        notifier = TelegramNotifier(bot_token=self.bot_token, chat_id=str(chat_id))

        quizzes_processed = 0
        assignments_notified = 0

        logger.info(f"Scanning student: {user.get('student_name', 'Student')} ({email})")

        client = LexytaAPIClient(email, password)
        if not client.signin():
            logger.error(f"Authentication failed for student {email}")
            return {"quizzes": 0, "assignments": 0}

        solver = GeminiQuizSolver(gemini_key)
        programs = client.get_enrolled_programs() or []

        for prog in programs:
            prog_id = prog["id"]
            classes = client.get_program_classes(prog_id) or []
            classes_to_check = detect_active_classes(classes, sem_filter)

            for cls in classes_to_check:
                class_id = cls["id"]
                class_name = cls.get("name", "Unknown Class")
                items = client.get_class_assignments(class_id) or []

                for item in items:
                    item_id = item["id"]
                    item_name = item.get("name", "Untitled")
                    item_type = item.get("type", "DOCUMENT")
                    due_date = item.get("due_date")
                    latest_attempt = item.get("latest_attempt")
                    status = latest_attempt.get("status") if latest_attempt else "NOT_ATTEMPTED"
                    overdue = is_overdue(due_date)
                    max_score = item.get("max_score")

                    # 1. Check for newly released grades/marks
                    if latest_attempt:
                        grade_obj = latest_attempt.get("grade")
                        if grade_obj and grade_obj.get("released"):
                            grade_val = grade_obj.get("grade")
                            if grade_val is not None and not self.user_manager.is_grade_notified(chat_id, item_id):
                                grader_name = ""
                                graded_by = grade_obj.get("graded_by")
                                if graded_by:
                                    grader_name = f"{graded_by.get('first_name', '')} {graded_by.get('last_name', '')}".strip()

                                pct_str = f" ({(grade_val/max_score)*100:.1f}%)" if max_score else ""
                                grade_msg = (
                                    f"📊 <b>LMS Marks / Result Released!</b>\n\n"
                                    f"📚 <b>Subject:</b> {class_name}\n"
                                    f"📝 <b>Item:</b> {item_name}\n"
                                    f"🎯 <b>Marks:</b> {grade_val} / {max_score or 'N/A'}{pct_str}\n"
                                )
                                if grader_name:
                                    grade_msg += f"👨‍🏫 <b>Evaluator:</b> {grader_name}\n"
                                grade_msg += "\n🌐 https://lms.lexyta.com"

                                if not dry_run:
                                    notifier.send(grade_msg)
                                    self.user_manager.mark_grade_notified(chat_id, item_id)

                    # 2. QUIZ WORKFLOW
                    if item_type == "QUIZ":
                        if status in ["COMPLETED", "GRADED"]:
                            continue
                        if self.user_manager.is_quiz_solved(chat_id, item_id):
                            continue
                        if overdue:
                            continue

                        logger.info(f"[QUIZ FOUND] {class_name} | {item_name}")

                        if not dry_run:
                            # Start attempt
                            if status == "NOT_ATTEMPTED":
                                client.start_quiz_attempt(class_id, item_id)

                            sections = client.get_quiz_questions(class_id, item_id)
                            if sections:
                                answers = solver.solve_quiz(sections)
                                if answers and client.submit_quiz_answers(class_id, item_id, answers):
                                    self.user_manager.mark_quiz_solved(chat_id, item_id)
                                    quizzes_processed += 1

                                    quiz_msg = (
                                        f"🎉 <b>LMS Quiz Auto-Solved & Submitted!</b>\n\n"
                                        f"📚 <b>Subject:</b> {class_name}\n"
                                        f"📝 <b>Quiz:</b> {item_name}\n"
                                        f"✅ <b>Status:</b> Solved with Gemini AI & Submitted\n"
                                        f"\n🌐 https://lms.lexyta.com"
                                    )
                                    notifier.send(quiz_msg)

                    # 3. ASSIGNMENT WORKFLOW
                    else:
                        if status in ["COMPLETED", "GRADED"]:
                            continue
                        if self.user_manager.is_assignment_notified(chat_id, item_id):
                            continue

                        if not overdue:
                            formatted_due = format_datetime_ist(due_date)
                            asgn_msg = (
                                f"📢 <b>LMS New Assignment Alert!</b>\n\n"
                                f"📚 <b>Subject:</b> {class_name}\n"
                                f"📝 <b>Assignment:</b> {item_name}\n"
                                f"⏰ <b>Due Date & Time:</b> {formatted_due}\n\n"
                                f"🌐 Open LMS: https://lms.lexyta.com"
                            )
                            if not dry_run:
                                notifier.send(asgn_msg)
                                self.user_manager.mark_assignment_notified(chat_id, item_id)
                                assignments_notified += 1
                        else:
                            self.user_manager.mark_assignment_notified(chat_id, item_id)

        return {"quizzes": quizzes_processed, "assignments": assignments_notified}

    def scan_all_active_users(self, dry_run: bool = False):
        """Scans all registered active users."""
        users = self.user_manager.get_all_active_users()
        logger.info(f"Starting multi-user scan for {len(users)} registered students...")

        for u in users:
            try:
                self.scan_user(u, dry_run=dry_run)
            except Exception as e:
                logger.error(f"Error scanning student {u.get('email')}: {e}")
