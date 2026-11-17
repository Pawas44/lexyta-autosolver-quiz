"""
Multi-User Registration & Storage Manager
Persists student credentials, settings, and scan states in data/users.json
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger("UserManager")

class UserManager:
    def __init__(self, file_path: str = "data/users.json"):
        self.file_path = file_path
        self._ensure_dir()
        self.users: Dict[str, Dict[str, Any]] = self._load()

    def _ensure_dir(self):
        dir_name = os.path.dirname(self.file_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

    def _load(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading users file: {e}")
        return {}

    def save(self):
        self._ensure_dir()
        temp_file = f"{self.file_path}.tmp"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.users, f, indent=2)
            os.replace(temp_file, self.file_path)
        except Exception as e:
            logger.error(f"Error saving users file: {e}")

    def get_user(self, chat_id: Any) -> Optional[Dict[str, Any]]:
        return self.users.get(str(chat_id))

    def get_all_active_users(self) -> List[Dict[str, Any]]:
        return [u for u in self.users.values() if u.get("is_active", True)]

    def add_user(self, chat_id: Any, email: str, password: str, gemini_api_key: str = "", student_name: str = "Student", **kwargs):
        """Convenience method to register a student with credentials."""
        data = {
            "email": email,
            "password": password,
            "gemini_api_key": gemini_api_key,
            "student_name": student_name,
            **kwargs
        }
        self.register_or_update_user(chat_id, data)

    def register_or_update_user(self, chat_id: Any, data: Dict[str, Any]):
        cid = str(chat_id)
        if cid not in self.users:
            self.users[cid] = {
                "chat_id": int(cid),
                "registered_at": datetime.now(timezone.utc).isoformat(),
                "is_active": True,
                "solved_quizzes": [],
                "notified_assignments": [],
                "notified_grades": []
            }
        
        self.users[cid].update(data)
        self.users[cid]["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.save()

    def set_user_active(self, chat_id: Any, is_active: bool) -> bool:
        cid = str(chat_id)
        if cid in self.users:
            self.users[cid]["is_active"] = is_active
            self.save()
            return True
        return False

    def delete_user(self, chat_id: Any) -> bool:
        cid = str(chat_id)
        if cid in self.users:
            del self.users[cid]
            self.save()
            return True
        return False

    def is_quiz_solved(self, chat_id: Any, quiz_id: str) -> bool:
        user = self.get_user(chat_id)
        return bool(user and quiz_id in user.get("solved_quizzes", []))

    def mark_quiz_solved(self, chat_id: Any, quiz_id: str):
        cid = str(chat_id)
        if cid in self.users:
            if "solved_quizzes" not in self.users[cid]:
                self.users[cid]["solved_quizzes"] = []
            if quiz_id not in self.users[cid]["solved_quizzes"]:
                self.users[cid]["solved_quizzes"].append(quiz_id)
                self.save()

    def is_assignment_notified(self, chat_id: Any, assignment_id: str) -> bool:
        user = self.get_user(chat_id)
        return bool(user and assignment_id in user.get("notified_assignments", []))

    def mark_assignment_notified(self, chat_id: Any, assignment_id: str):
        cid = str(chat_id)
        if cid in self.users:
            if "notified_assignments" not in self.users[cid]:
                self.users[cid]["notified_assignments"] = []
            if assignment_id not in self.users[cid]["notified_assignments"]:
                self.users[cid]["notified_assignments"].append(assignment_id)
                self.save()

    def is_grade_notified(self, chat_id: Any, item_id: str) -> bool:
        user = self.get_user(chat_id)
        return bool(user and item_id in user.get("notified_grades", []))

    def mark_grade_notified(self, chat_id: Any, item_id: str):
        cid = str(chat_id)
        if cid in self.users:
            if "notified_grades" not in self.users[cid]:
                self.users[cid]["notified_grades"] = []
            if item_id not in self.users[cid]["notified_grades"]:
                self.users[cid]["notified_grades"].append(item_id)
                self.save()
