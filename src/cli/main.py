"""
LMS Lexyta Auto Quiz Solver & Assignment Notifier - CLI Interface.
"""

import sys
import time
import argparse
import logging

from src.core.config import AppConfig
from src.core.state import StateManager
from src.core.logger import setup_logger
from src.client.lexyta_api import LexytaAPIClient
from src.solvers.gemini_solver import GeminiQuizSolver
from src.notifiers.dispatcher import NotificationDispatcher
from src.engine.scanner import LMSScanner

setup_logger()
logger = logging.getLogger("CLI")

def test_login(config: AppConfig):
    """Tests authentication to Lexyta LMS and prints student info."""
    logger.info(f"Testing login for {config.email}...")
    client = LexytaAPIClient(config.email, config.password)
    try:
        client.signin()
        profile = client.get_profile()
        print("\n" + "="*50)
        print("  LEXTYA LMS LOGIN VERIFICATION")
        print("="*50)
        print(f"  Name:       {profile.get('first_name')} {profile.get('last_name')}")
        print(f"  Email:      {profile.get('email')}")
        print(f"  Student ID: {profile.get('id')}")
        programs = client.get_enrolled_programs()
        print(f"  Enrolled:   {len(programs)} Program(s)")
        for p in programs:
            print(f"   - {p.get('name')} ({p.get('id')})")
        print("="*50)
        print("SUCCESS: Credentials verified!\n")
    except Exception as e:
        logger.error(f"Login verification failed: {e}")
        sys.exit(1)

def test_ai(config: AppConfig):
    """Tests Gemini AI connection and solving capability with sample academic question."""
    logger.info("Testing Gemini AI solver...")
    solver = GeminiQuizSolver(config.gemini_api_key, config.gemini_models)
    sample_sections = [
        {
            "name": "Test Section",
            "questions": [
                {
                    "id": "q1",
                    "question_type": "SINGLE_CHOICE",
                    "text": "<p>In Python, which built-in data type is mutable?</p>",
                    "options": [
                        {"id": "opt_tuple", "label": "A", "text": "tuple"},
                        {"id": "opt_list", "label": "B", "text": "list"},
                        {"id": "opt_str", "label": "C", "text": "str"},
                        {"id": "opt_int", "label": "D", "text": "int"}
                    ]
                }
            ]
        }
    ]
    result = solver.solve_quiz(sample_sections)
    print("\n" + "="*50)
    print("  GEMINI AI SOLVER TEST")
    print("="*50)
    print(f"  Result: {result}")
    if result.get("q1") == "opt_list":
        print("SUCCESS: Gemini AI correctly answered question (Selected: opt_list / list)!")
    else:
        print(f"Output received: {result.get('q1')}")
    print("="*50 + "\n")

def test_notify(config: AppConfig):
    """Tests notification dispatch to all enabled channels (Telegram, Termux, etc.)."""
    logger.info("Testing notification dispatch...")
    dispatcher = NotificationDispatcher(config)
    if not dispatcher.notifiers:
        print("\nWARNING: No notification channels are currently enabled in config/config.json!\n")
        return
    dispatcher.notify_assignment(
        subject="TEST_SUBJECT",
        assignment_name="Sample Assignment (Alert Verification)",
        due_date="2026-11-20",
        details="This is a test notification to verify your Telegram alert setup is working."
    )
    print("\nSUCCESS: Test notification sent to all active channels!\n")

def interactive_setup():
    """Interactive wizard to configure the bot for any student."""
    import os
    import json
    from src.core.config import DEFAULT_GEMINI_KEY

    print("\n" + "="*60)
    print("  🎓 LMS LEXYTA AUTO-SOLVER & NOTIFIER - SETUP WIZARD")
    print("="*60)
    print("This wizard will help you configure your credentials and alert settings.\n")

    email = input("1. Enter Lexyta LMS Email: ").strip()
    while not email:
        email = input("   Email cannot be empty: ").strip()

    password = input("2. Enter Lexyta LMS Password: ").strip()
    while not password:
        password = input("   Password cannot be empty: ").strip()

    gemini_key = input("3. Enter Gemini API Key (press Enter for default): ").strip()
    if not gemini_key:
        gemini_key = DEFAULT_GEMINI_KEY

    print("\n--- Telegram Notification Setup ---")
    print("(Create a bot with @BotFather and get your Chat ID from @userinfobot)")
    tg_token = input("4. Enter Telegram Bot Token: ").strip()
    tg_chat_id = input("5. Enter Telegram Chat ID: ").strip()

    phone = input("6. Enter your Mobile Number [default: 9315135782]: ").strip() or "9315135782"
    semester = input("7. Enter Semester Filter (e.g. BCA3, BCA1, or press Enter for all): ").strip() or "BCA3"

    cfg_dict = {
        "email": email,
        "password": password,
        "phone_number": phone,
        "country_code": "+91",
        "check_interval_minutes": 15,
        "gemini_api_key": gemini_key,
        "gemini_models": [
            "gemini-3.1-flash-lite",
            "gemini-3.8-flash",
            "gemini-flash-latest"
        ],
        "active_semester_filter": semester,
        "skip_overdue_quizzes": True,
        "auto_solve_quizzes": True,
        "notifications": {
            "whatsapp_callmebot": {
                "enabled": False,
                "api_key": ""
            },
            "fast2sms": {
                "enabled": False,
                "api_key": ""
            },
            "telegram": {
                "enabled": bool(tg_token and tg_chat_id),
                "bot_token": tg_token,
                "chat_id": tg_chat_id
            },
            "termux": {
                "enabled": True
            }
        }
    }

    os.makedirs("config", exist_ok=True)
    with open("config/config.json", "w", encoding="utf-8") as f:
        json.dump(cfg_dict, f, indent=2)

    print("\n" + "="*60)
    print("SUCCESS: Configuration saved to config/config.json!")
    print("="*60)

    test_ans = input("\nWould you like to test LMS login now? (y/n): ").strip().lower()
    if test_ans in ["y", "yes"]:
        test_cfg = AppConfig.load("config/config.json")
        test_login(test_cfg)

    if tg_token and tg_chat_id:
        tg_test = input("Would you like to send a test alert to Telegram? (y/n): ").strip().lower()
        if tg_test in ["y", "yes"]:
            test_cfg = AppConfig.load("config/config.json")
            test_notify(test_cfg)

    print("\nSetup complete! You can now run the bot with: python run.py\n")

def run_cli():
    import os
    parser = argparse.ArgumentParser(
        prog="lexyta-bot",
        description="LMS Lexyta Auto Quiz Solver & Assignment Notifier"
    )
    parser.add_argument("--setup", action="store_true", help="Launch interactive setup wizard")
    parser.add_argument("--once", action="store_true", help="Run one scan pass and exit (ideal for Cron / GitHub Actions)")
    parser.add_argument("--dry-run", action="store_true", help="Run without submitting quizzes or sending SMS")
    parser.add_argument("--interval", type=int, default=None, help="Check interval in minutes (default from config)")
    parser.add_argument("--test-login", action="store_true", help="Test Lexyta LMS login")
    parser.add_argument("--test-ai", action="store_true", help="Test Gemini AI quiz solver")
    parser.add_argument("--test-notify", action="store_true", help="Send a test alert to verify Telegram / SMS setup")
    parser.add_argument("--config", type=str, default=None, help="Path to custom config.json")
    args = parser.parse_args()

    config = AppConfig.load(args.config)
    state = StateManager()

    if args.setup:
        interactive_setup()
        return

    if not config.email or not config.password:
        import sys
        if sys.stdin.isatty():
            print("\n[!] No configuration file found.")
            interactive_setup()
            return
        else:
            logger.warning("No LMS credentials found (config.json missing and LMS_EMAIL/LMS_PASSWORD not set).")
            logger.info("In GitHub Actions, add LMS_EMAIL and LMS_PASSWORD to Repository Secrets.")
            return

    if args.test_login:
        test_login(config)
        return

    if args.test_ai:
        test_ai(config)
        return

    if args.test_notify:
        test_notify(config)
        return

    client = LexytaAPIClient(config.email, config.password)
    solver = GeminiQuizSolver(config.gemini_api_key, config.gemini_models)
    notifier = NotificationDispatcher(config)
    scanner = LMSScanner(config, state, client, solver, notifier)

    interval = args.interval or config.check_interval_minutes

    if args.once:
        scanner.scan(dry_run=args.dry_run)
    else:
        # Start lightweight HTTP health-check server if deployed on Render/Cloud Web Service
        if os.getenv("PORT"):
            from http.server import HTTPServer, BaseHTTPRequestHandler
            import threading

            class CloudHealthHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"OK - Lexyta LMS AutoSolver Daemon is running 24/7!\n")

                def log_message(self, format, *args):
                    pass

            def run_cloud_health():
                port = int(os.getenv("PORT", 10000))
                try:
                    srv = HTTPServer(("0.0.0.0", port), CloudHealthHandler)
                    logger.info(f"Health-check HTTP server listening on 0.0.0.0:{port} (Render / Cloud ready)")
                    srv.serve_forever()
                except Exception as e:
                    logger.error(f"Failed to bind health-check HTTP server: {e}")

            threading.Thread(target=run_cloud_health, daemon=True).start()

        logger.info(f"Starting continuous daemon loop. Checking every {interval} minutes...")
        while True:
            try:
                scanner.scan(dry_run=args.dry_run)
            except Exception as e:
                logger.error(f"Error during scan loop: {e}", exc_info=True)

            logger.info(f"Sleeping for {interval} minutes...\n")
            time.sleep(interval * 60)

if __name__ == "__main__":
    run_cli()
