#!/usr/bin/env python3
"""
Lexyta LMS Multi-User Telegram Bot Server & Autonomous Scanner
Hosts the master Telegram Bot (@... ) that onboards any student via /start,
stores their credentials, and runs 24/7 background scans to solve quizzes
and send instant assignment & mark alerts.
"""

import sys
import os
import time
import threading
import logging

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.core.logger import setup_logger
from src.core.user_manager import UserManager
from src.bot.telegram_server import TelegramServer, MASTER_BOT_TOKEN
from src.engine.multi_scanner import MultiScanner

setup_logger()
logger = logging.getLogger("MasterServer")

CHECK_INTERVAL_MINUTES = 15

def background_scanner_loop(scanner: MultiScanner):
    """Background daemon thread scanning all registered students periodically."""
    logger.info(f"Background multi-user scanner started. Interval: {CHECK_INTERVAL_MINUTES} minutes.")
    while True:
        try:
            scanner.scan_all_active_users()
        except Exception as e:
            logger.error(f"Error in background scanner cycle: {e}", exc_info=True)

        logger.info(f"Sleeping for {CHECK_INTERVAL_MINUTES} minutes until next multi-user scan...\n")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)

def main():
    logger.info("="*60)
    logger.info(" Starting Lexyta LMS Multi-User Autonomous Telegram Server")
    logger.info("="*60)

    token = os.getenv("MASTER_BOT_TOKEN") or MASTER_BOT_TOKEN
    user_manager = UserManager("data/users.json")
    scanner = MultiScanner(user_manager=user_manager, bot_token=token)
    bot_server = TelegramServer(bot_token=token, user_manager=user_manager)

    # Attach on-demand scan callback to bot for /scan command
    def on_demand_scan(chat_id: int):
        user = user_manager.get_user(chat_id)
        if user:
            return scanner.scan_user(user)
        return {"quizzes": 0, "assignments": 0}

    bot_server.on_demand_scanner = on_demand_scan

    # Start background scanner thread
    t = threading.Thread(target=background_scanner_loop, args=(scanner,), daemon=True)
    t.start()

    # Start Telegram bot polling on main thread
    try:
        bot_server.poll()
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")

if __name__ == "__main__":
    main()
