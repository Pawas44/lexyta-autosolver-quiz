"""
Configuration Loader
Loads settings from config/config.json, root config.json, or environment variables.
"""

import os
import json
from dataclasses import dataclass, field
from typing import Dict, Any, List

DEFAULT_GEMINI_KEY = "AQ.Ab8RN6KBj3AWE6ny111gstjEQ97RNofqLMEaUTtnGCQJUJUyqg"
DEFAULT_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite-preview",
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-flash-latest"
]

@dataclass
class AppConfig:
    email: str = "pawasnishant1327@gmail.com"
    password: str = "p7l8PQOI!\\"
    phone_number: str = ""
    country_code: str = "+91"
    check_interval_minutes: int = 5
    gemini_api_key: str = DEFAULT_GEMINI_KEY
    gemini_models: List[str] = field(default_factory=lambda: list(DEFAULT_MODELS))
    active_semester_filter: str = "auto"
    skip_overdue_quizzes: bool = True
    auto_solve_quizzes: bool = True
    notifications: Dict[str, Any] = field(default_factory=lambda: {
        "telegram": {
            "enabled": True,
            "bot_token": "9029165430:AAHDFq9dIBa_GzpBUzokzsPaX-tBWZDMwcw",
            "chat_id": "8224782152"
        },
        "termux": {
            "enabled": True
        }
    })

    @classmethod
    def load(cls, config_path: str = None) -> "AppConfig":
        """Loads configuration from JSON file or environment variables."""
        data = {}

        candidate_paths = [
            config_path,
            "config/config.json",
            "config.json"
        ]

        for path in candidate_paths:
            if path and os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    break
                except Exception:
                    pass

        email = os.getenv("LMS_EMAIL") or data.get("email", "pawasnishant1327@gmail.com")
        
        raw_pwd = os.getenv("LMS_PASSWORD")
        if raw_pwd:
            # Handle shell or YAML escaped trailing backslash
            if raw_pwd.endswith(r"\\"):
                password = raw_pwd[:-1]
            else:
                password = raw_pwd
        else:
            password = data.get("password", "p7l8PQOI!\\")

        phone_number = os.getenv("TARGET_PHONE") or data.get("phone_number", "")
        country_code = os.getenv("COUNTRY_CODE") or data.get("country_code", "+91")
        check_interval = int(os.getenv("CHECK_INTERVAL") or data.get("check_interval_minutes", 5))
        gemini_key = os.getenv("GEMINI_API_KEY") or data.get("gemini_api_key", DEFAULT_GEMINI_KEY)
        if not gemini_key:
            gemini_key = DEFAULT_GEMINI_KEY

        models = data.get("gemini_models", DEFAULT_MODELS)
        semester_filter = os.getenv("SEMESTER_FILTER", data.get("active_semester_filter", "BCA3"))
        skip_overdue = data.get("skip_overdue_quizzes", True)
        auto_solve = data.get("auto_solve_quizzes", True)
        notifications = data.get("notifications", {
            "whatsapp_callmebot": {"enabled": False, "api_key": ""},
            "fast2sms": {"enabled": False, "api_key": ""},
            "telegram": {"enabled": True, "bot_token": "9029165430:AAHDFq9dIBa_GzpBUzokzsPaX-tBWZDMwcw", "chat_id": "8224782152"},
            "termux": {"enabled": True}
        })

        # Allow environment overrides for Telegram
        tg_token_env = os.getenv("TELEGRAM_BOT_TOKEN")
        tg_chat_env = os.getenv("TELEGRAM_CHAT_ID")
        if tg_token_env:
            notifications["telegram"]["bot_token"] = tg_token_env
            notifications["telegram"]["enabled"] = True
        if tg_chat_env:
            notifications["telegram"]["chat_id"] = tg_chat_env
            notifications["telegram"]["enabled"] = True

        return cls(
            email=email,
            password=password,
            phone_number=phone_number,
            country_code=country_code,
            check_interval_minutes=check_interval,
            gemini_api_key=gemini_key,
            gemini_models=models,
            active_semester_filter=semester_filter,
            skip_overdue_quizzes=skip_overdue,
            auto_solve_quizzes=auto_solve,
            notifications=notifications
        )

    def save(self, target_path: str = "config/config.json"):
        """Saves current configuration to a JSON file."""
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(self.__dict__, f, indent=2)
