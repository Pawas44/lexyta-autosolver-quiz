"""
Multi-Tenant LMS Scanner
Iterates over all registered students, solves quizzes, alerts on assignments and marks.
"""

import time
import logging
from typing import Dict, Any, Optional

from src.core.user_manager import UserManager
from src.core.access_control import AccessController
from src.client.lexyta_api import LexytaAPIClient
from src.solvers.gemini_solver import GeminiQuizSolver
from src.solvers.human_pacer import calculate_target_duration_seconds, wait_with_human_pacing
from src.notifiers.telegram import TelegramNotifier, format_quiz_progress_msg, format_quiz_submitted_msg
from src.notifiers.dispatcher import format_datetime_ist
from src.engine.scanner import is_overdue, detect_active_classes
from src.core.config import DEFAULT_GEMINI_KEY

logger = logging.getLogger("MultiScanner")

class MultiScanner:
    def __init__(self, user_manager: UserManager, bot_token: str, access_controller: Optional[AccessController] = None):
        self.user_manager = user_manager
        self.bot_token = bot_token
        self.access_controller = access_controller

    def scan_user(self, user: Dict[str, Any], dry_run: bool = False) -> Dict[str, int]:
        """Scans LMS for a single student."""
        chat_id = user["chat_id"]
        email = user["email"]
        password = user["password"]
        student_name = user.get("student_name", "Student")
        gemini_key = user.get("gemini_api_key") or DEFAULT_GEMINI_KEY
        sem_filter = user.get("semester_filter", "auto")
        notifier = TelegramNotifier(bot_token=self.bot_token, chat_id=str(chat_id))

        student_hdr = f"👤 <b>Student:</b> {student_name} (<code>{email}</code>)\n"
        seen_in_pass = set()

        quizzes_processed = 0
        assignments_notified = 0

        logger.info(f"Scanning student: {student_name} ({email}) [chat_id: {chat_id}]")

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
                    if item_id in seen_in_pass:
                        continue
                    seen_in_pass.add(item_id)

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
                            # Only notify if grade exists AND we haven't notified yet
                            if grade_val is not None and not self.user_manager.is_grade_notified(chat_id, item_id):
                                import datetime as _dt
                                rel_str = grade_obj.get("released_at") or grade_obj.get("updated_at") or grade_obj.get("created_at")
                                if rel_str:
                                    try:
                                        rel_time = _dt.datetime.fromisoformat(rel_str.replace("Z", "+00:00"))
                                        # Extra safety: skip if grade was released more than 24h ago (stale)
                                        if (_dt.datetime.now(_dt.timezone.utc) - rel_time).total_seconds() > 86400:
                                            self.user_manager.mark_grade_notified(chat_id, item_id)
                                            continue
                                    except Exception:
                                        pass
                                else:
                                    # No timestamp: mark silently to prevent ancient grade spam
                                    self.user_manager.mark_grade_notified(chat_id, item_id)
                                    continue

                                grader_name = ""
                                graded_by = grade_obj.get("graded_by")
                                if graded_by:
                                    grader_name = f"{graded_by.get('first_name', '')} {graded_by.get('last_name', '')}".strip()

                                pct_str = f" ({(grade_val/max_score)*100:.1f}%)" if max_score else ""
                                grade_msg = (
                                    f"📊 <b>LMS Marks / Result Released!</b>\n\n"
                                    f"{student_hdr}"
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

                    # 2. QUIZ / GRAND QUIZ WORKFLOW
                    is_quiz = (item_type in ["QUIZ", "EXAM", "TEST", "ASSESSMENT", "ONLINE_QUIZ"]) or \
                              (any(w in item_name.lower() for w in ["quiz", "grand"]) and item_type not in ["DOCUMENT", "HOMEWORK"])

                    if is_quiz:
                        if status in ["COMPLETED", "GRADED"]:
                            continue
                        if self.user_manager.is_quiz_solved(chat_id, item_id):
                            continue
                        if overdue:
                            continue

                        # Check if user has auto-solve enabled or paused
                        auto_solve_enabled = user.get("auto_solve", True)
                        if not auto_solve_enabled:
                            if not self.user_manager.is_quiz_notified(chat_id, item_id):
                                manual_alert = (
                                    f"📢 <b>LMS Quiz Available!</b>\n\n"
                                    f"{student_hdr}"
                                    f"📚 <b>Subject:</b> {class_name}\n"
                                    f"📝 <b>Quiz:</b> {item_name}\n"
                                    f"⏰ <b>Status:</b> {status}\n\n"
                                    f"<i>ℹ️ Auto-Solve aapke account ke liye PAUSED hai. Bot ise solve nahi karega.</i>\n"
                                    f"<i>Agar bot se solve karwana hai toh type karein: /solve ya /resume</i>"
                                )
                                notifier.send(manual_alert)
                                self.user_manager.mark_quiz_notified(chat_id, item_id)
                            continue

                        logger.info(f"[QUIZ FOUND] {student_name} | {class_name} | {item_name}")

                        if not dry_run:
                            t_start = time.time()
                            # 1. Send initial Telegram alert
                            init_msg = (
                                f"🚀 <b>LMS Quiz Detected & Started!</b>\n\n"
                                f"{student_hdr}"
                                f"📚 <b>Subject:</b> {class_name}\n"
                                f"📝 <b>Quiz:</b> {item_name}\n"
                                f"⏳ <b>Status:</b> Initializing attempt and downloading questions..."
                            )
                            prog_msg_id = notifier.send_message(init_msg)

                            # 2. Start attempt
                            if status == "NOT_ATTEMPTED":
                                client.start_quiz_attempt(class_id, item_id)

                            sections = client.get_quiz_questions(class_id, item_id)
                            if sections:
                                total_q = sum(len(s.get("questions", [])) for s in sections)
                                if prog_msg_id:
                                    notifier.edit_message(
                                        prog_msg_id,
                                        format_quiz_progress_msg(class_name, item_name, 0, total_q, f"Found {total_q} questions. Gemini AI solver running...", student_name=student_name)
                                    )

                                def on_progress(completed: int, total: int, step_desc: str):
                                    if prog_msg_id:
                                        notifier.edit_message(
                                            prog_msg_id,
                                            format_quiz_progress_msg(class_name, item_name, completed, total, step_desc, student_name=student_name)
                                        )

                                answers = solver.solve_quiz(sections, on_progress=on_progress)
                                if answers:
                                    # Realistic human pacing (e.g. ~35s per question with human variance)
                                    time_limit = item.get("time_limit")
                                    target_dur = calculate_target_duration_seconds(time_limit, total_q, due_date_str=due_date)

                                    def on_pace_tick(elapsed_sec: float, remaining_sec: float, status_str: str):
                                        if prog_msg_id:
                                            notifier.edit_message(
                                                prog_msg_id,
                                                format_quiz_progress_msg(class_name, item_name, len(answers), total_q, status_str, student_name=student_name)
                                            )

                                    wait_with_human_pacing(t_start, target_dur, on_tick=on_pace_tick, tick_interval=15.0, total_questions=total_q)

                                    if client.submit_quiz_answers(class_id, item_id, answers):
                                        elapsed = time.time() - t_start
                                        self.user_manager.mark_quiz_solved(chat_id, item_id)
                                        quizzes_processed += 1

                                        final_msg = format_quiz_submitted_msg(class_name, item_name, len(answers), total_q, elapsed, student_name=student_name)
                                        if prog_msg_id:
                                            notifier.edit_message(prog_msg_id, final_msg)
                                        else:
                                            notifier.send(final_msg)
                                    else:
                                        if prog_msg_id:
                                            notifier.edit_message(prog_msg_id, f"❌ Submission failed for <b>{item_name}</b>.")

                    # 3. ASSIGNMENT WORKFLOW
                    else:
                        if status in ["COMPLETED", "GRADED"]:
                            continue
                        if overdue:
                            continue
                        if self.user_manager.is_assignment_notified(chat_id, item_id):
                            continue
                        # Skip if user already has a submission (server-side check)
                        if latest_attempt and latest_attempt.get("status") in ["IN_PROGRESS", "SUBMITTED"]:
                            self.user_manager.mark_assignment_notified(chat_id, item_id)
                            continue

                        formatted_due = format_datetime_ist(due_date)
                        asgn_msg = (
                            f"📢 <b>LMS New Assignment Alert!</b>\n\n"
                            f"{student_hdr}"
                            f"📚 <b>Subject:</b> {class_name}\n"
                            f"📝 <b>Assignment:</b> {item_name}\n"
                            f"⏰ <b>Due Date & Time:</b> {formatted_due}\n\n"
                            f"🌐 Open LMS: https://lms.lexyta.com"
                        )
                        if not dry_run:
                            notifier.send(asgn_msg)
                            self.user_manager.mark_assignment_notified(chat_id, item_id)
                            assignments_notified += 1

        return {"quizzes": quizzes_processed, "assignments": assignments_notified}

    def scan_all_active_users(self, dry_run: bool = False):
        """Scans all registered active users."""
        users = self.user_manager.get_all_active_users()
        logger.info(f"Starting multi-user scan for {len(users)} registered students...")

        try:
            for u in users:
                cid = u.get("chat_id")
                if self.access_controller and not self.access_controller.is_allowed(cid):
                    logger.info(f"Skipping student {u.get('email')} (chat_id {cid} is not in allowed list)")
                    continue
                try:
                    self.scan_user(u, dry_run=dry_run)
                except Exception as e:
                    logger.error(f"Error scanning student {u.get('email')}: {e}")
        finally:
            # Batch flush dirty state to cloud in a single commit, preventing deploy loops
            try:
                self.user_manager.flush_cloud_state()
            except Exception as fe:
                logger.warning(f"Error flushing cloud state: {fe}")
