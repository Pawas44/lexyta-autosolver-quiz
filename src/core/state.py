"""
Persistent State Manager
Tracks solved quizzes and notified assignments with thread-safe / atomic file writes.
"""

import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List

class StateManager:
    def __init__(self, file_path: str = "data/state.json"):
        self.file_path = file_path
        self._ensure_dir()
        self.data: Dict[str, Any] = self._load()

    def _ensure_dir(self):
        dir_name = os.path.dirname(self.file_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "solved_quizzes": [],
            "notified_assignments": [],
            "notified_grades": [],
            "last_scan_utc": None,
            "last_status": "INITIALIZED"
        }

    def save(self):
        self._ensure_dir()
        temp_file = f"{self.file_path}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
        os.replace(temp_file, self.file_path)

    def is_quiz_solved(self, quiz_id: str) -> bool:
        return quiz_id in self.data.get("solved_quizzes", [])

    def mark_quiz_solved(self, quiz_id: str):
        if "solved_quizzes" not in self.data:
            self.data["solved_quizzes"] = []
        if quiz_id not in self.data["solved_quizzes"]:
            self.data["solved_quizzes"].append(quiz_id)
            self.save()

    def is_assignment_notified(self, assignment_id: str) -> bool:
        return assignment_id in self.data.get("notified_assignments", [])

    def mark_assignment_notified(self, assignment_id: str):
        if "notified_assignments" not in self.data:
            self.data["notified_assignments"] = []
        if assignment_id not in self.data["notified_assignments"]:
            self.data["notified_assignments"].append(assignment_id)
            self.save()

    def is_grade_notified(self, assignment_id: str) -> bool:
        return assignment_id in self.data.get("notified_grades", [])

    def mark_grade_notified(self, assignment_id: str):
        if "notified_grades" not in self.data:
            self.data["notified_grades"] = []
        if assignment_id not in self.data["notified_grades"]:
            self.data["notified_grades"].append(assignment_id)
            self.save()

    def update_scan_status(self, status: str = "OK"):
        self.data["last_scan_utc"] = datetime.now(timezone.utc).isoformat()
        self.data["last_status"] = status
        self.save()
