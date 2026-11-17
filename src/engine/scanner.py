"""
LMS Scanning & Orchestration Engine
Scans subjects, identifies new quizzes and assignments, triggers AI solving and sends alerts.
"""

import re
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from src.core.config import AppConfig
from src.core.state import StateManager
from src.client.lexyta_api import LexytaAPIClient
from src.solvers.gemini_solver import GeminiQuizSolver
from src.notifiers.dispatcher import NotificationDispatcher

logger = logging.getLogger("LMSScanner")

def is_overdue(due_date_str: Optional[str]) -> bool:
    """Checks whether the ISO due date string has already passed."""
    if not due_date_str:
        return False
    try:
        clean_date = due_date_str.replace("Z", "+00:00")
        due = datetime.fromisoformat(clean_date)
        return due < datetime.now(timezone.utc)
    except Exception:
        return False

def detect_active_classes(classes: List[Dict[str, Any]], active_filter: str) -> List[Dict[str, Any]]:
    """
    Intelligently selects active semester classes.
    If active_filter is 'auto', empty, or 'latest', it automatically discovers
    the highest semester enrolled (e.g. BCA3 -> BCA4 -> BCA5).
    Zero manual upgrade needed when moving to a new semester!
    """
    if not classes:
        return []

    clean_filter = active_filter.strip().lower() if active_filter else "auto"

    # Specific manual filter override (e.g. "bca2", "os")
    if clean_filter not in ["auto", "latest", "all", ""]:
        filtered = [c for c in classes if clean_filter in c.get("name", "").lower()]
        if filtered:
            return filtered

    if clean_filter == "all":
        return classes

    # AUTO: Parse semester numbers from subject codes (e.g. BCA1, BCA2, BCA3...)
    sem_data = []
    for cls in classes:
        name = cls.get("name", "")
        match = re.search(r'([a-zA-Z]+)(\d+)', name)
        if match:
            prefix = match.group(1).upper()
            sem_num = int(match.group(2))
            sem_data.append((prefix, sem_num, cls))

    if sem_data:
        max_sem_by_prefix = {}
        for prefix, num, _ in sem_data:
            if prefix not in max_sem_by_prefix or num > max_sem_by_prefix[prefix]:
                max_sem_by_prefix[prefix] = num

        auto_classes = [
            cls for prefix, num, cls in sem_data
            if num == max_sem_by_prefix.get(prefix)
        ]
        if auto_classes:
            detected_tags = [f"{p}{max_sem_by_prefix[p]}" for p in max_sem_by_prefix]
            logger.info(f"Auto-detected current active semester: {', '.join(detected_tags)} ({len(auto_classes)} subjects)")
            return auto_classes

    return classes

class LMSScanner:
    def __init__(self, config: AppConfig, state: StateManager, client: LexytaAPIClient, solver: GeminiQuizSolver, notifier: NotificationDispatcher):
        self.config = config
        self.state = state
        self.client = client
        self.solver = solver
        self.notifier = notifier

    def scan(self, dry_run: bool = False) -> Dict[str, Any]:
        """Executes one complete LMS scanning pass."""
        logger.info(f"--- Starting LMS Scan Pass ({'DRY RUN' if dry_run else 'LIVE'}) ---")

        if not self.client.ensure_authenticated():
            logger.error("Authentication check failed. Skipping this pass.")
            self.state.update_scan_status("AUTH_FAILED")
            return {"status": "AUTH_FAILED"}

        programs = self.client.get_enrolled_programs()
        if not programs:
            logger.warning("No enrolled programs found for this user.")
            self.state.update_scan_status("NO_PROGRAMS")
            return {"status": "NO_PROGRAMS"}

        active_filter = self.config.active_semester_filter.strip().lower()
        skip_overdue = self.config.skip_overdue_quizzes

        quizzes_processed = 0
        assignments_notified = 0

        for prog in programs:
            prog_id = prog["id"]
            prog_name = prog.get("name", "Unknown Program")
            logger.info(f"Checking Program: {prog_name} ({prog_id})")

            classes = self.client.get_program_classes(prog_id)
            classes_to_check = detect_active_classes(classes, active_filter)

            logger.info(f"Scanning {len(classes_to_check)} subjects...")

            for cls in classes_to_check:
                class_id = cls["id"]
                class_name = cls.get("name", "Unknown Class")

                items = self.client.get_class_assignments(class_id)
                if not items:
                    continue

                for item in items:
                    item_id = item["id"]
                    item_name = item.get("name", "Untitled")
                    item_type = item.get("type", "DOCUMENT")
                    due_date = item.get("due_date")
                    latest_attempt = item.get("latest_attempt")
                    status = latest_attempt.get("status") if latest_attempt else "NOT_ATTEMPTED"
                    overdue = is_overdue(due_date)
                    max_score = item.get("max_score")

                    # Check for newly released grades/marks
                    if latest_attempt:
                        grade_obj = latest_attempt.get("grade")
                        if grade_obj and grade_obj.get("released"):
                            grade_val = grade_obj.get("grade")
                            if grade_val is not None and not self.state.is_grade_notified(item_id):
                                grader_name = None
                                graded_by = grade_obj.get("graded_by")
                                if graded_by:
                                    grader_name = f"{graded_by.get('first_name', '')} {graded_by.get('last_name', '')}".strip()
                                
                                if dry_run:
                                    logger.info(f"[DRY RUN] Would notify marks for '{item_name}': {grade_val}/{max_score}")
                                else:
                                    logger.info(f"📢 New grade detected for '{item_name}': {grade_val}/{max_score}")
                                    self.notifier.notify_quiz_grade(
                                        subject=class_name,
                                        quiz_name=item_name,
                                        grade=grade_val,
                                        max_score=max_score,
                                        graded_by=grader_name
                                    )
                                    self.state.mark_grade_notified(item_id)

                    # ---------------------------------------------------------
                    # 1. QUIZ WORKFLOW
                    # ---------------------------------------------------------
                    if item_type == "QUIZ":
                        if status in ["COMPLETED", "GRADED"]:
                            continue
                        if self.state.is_quiz_solved(item_id):
                            continue
                        if overdue and skip_overdue:
                            continue

                        logger.info(f"\n[NEW QUIZ FOUND] Subject: {class_name} | Quiz: {item_name} | Due: {due_date}")

                        if dry_run:
                            logger.info(f"[DRY RUN] Would solve and submit quiz '{item_name}'")
                            quizzes_processed += 1
                            continue

                        # Start attempt if needed
                        if status == "NOT_ATTEMPTED":
                            start_res = self.client.start_quiz_attempt(class_id, item_id)
                            if not start_res:
                                logger.error(f"Failed to start attempt for '{item_name}'. Skipping.")
                                continue

                        # Fetch questions
                        sections = self.client.get_quiz_questions(class_id, item_id)
                        if not sections:
                            logger.error(f"Could not fetch questions for '{item_name}'. Skipping.")
                            continue

                        # Solve questions with Gemini AI
                        answers = self.solver.solve_quiz(sections)
                        if not answers:
                            logger.error(f"Failed to generate answers for '{item_name}'. Skipping.")
                            continue

                        # Submit answers to LMS
                        logger.info(f"Submitting {len(answers)} answers for '{item_name}'...")
                        success = self.client.submit_quiz_answers(class_id, item_id, answers)
                        if success:
                            logger.info(f"🎉 Quiz '{item_name}' SUBMITTED SUCCESSFULLY!")
                            self.state.mark_quiz_solved(item_id)
                            self.notifier.notify_quiz_solved(class_name, item_name)
                            quizzes_processed += 1
                        else:
                            logger.error(f"Submission failed for quiz '{item_name}'")

                    # ---------------------------------------------------------
                    # 2. ASSIGNMENT WORKFLOW
                    # ---------------------------------------------------------
                    else: # DOCUMENT / EXAM
                        if status in ["COMPLETED", "GRADED"]:
                            continue
                        if self.state.is_assignment_notified(item_id):
                            continue

                        logger.info(f"\n[NEW ASSIGNMENT FOUND] Subject: {class_name} | Title: {item_name} | Due: {due_date} | Overdue: {overdue}")

                        if not overdue:
                            details_text = ""
                            details_obj = self.client.get_assignment_details(class_id, item_id)
                            if details_obj:
                                desc = details_obj.get("description", "")
                                files = details_obj.get("files", [])
                                file_names = ", ".join([f["name"] for f in files]) if files else "None"
                                details_text = f"{desc} | Files: {file_names}"

                            if dry_run:
                                logger.info(f"[DRY RUN] Would alert phone {self.notifier.phone} for '{item_name}'")
                                assignments_notified += 1
                            else:
                                self.notifier.notify_assignment(
                                    subject=class_name,
                                    assignment_name=item_name,
                                    due_date=due_date,
                                    details=details_text
                                )
                                self.state.mark_assignment_notified(item_id)
                                assignments_notified += 1
                        else:
                            # Acknowledge overdue assignment without spamming
                            self.state.mark_assignment_notified(item_id)

        self.state.update_scan_status("OK")
        logger.info(f"Pass complete: {quizzes_processed} quizzes, {assignments_notified} assignments.")
        return {
            "status": "OK",
            "quizzes_processed": quizzes_processed,
            "assignments_notified": assignments_notified
        }
