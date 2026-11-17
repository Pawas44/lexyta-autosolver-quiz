#!/usr/bin/env python3
"""
Root entrypoint for LMS Lexyta Auto Quiz Solver & Assignment Notifier.
Usage:
  python run.py                   # Run in background daemon loop (every 15 min)
  python run.py --once            # Run single scan pass (ideal for cron/GitHub Actions)
  python run.py --dry-run --once  # Test scan without submitting or sending SMS
  python run.py --test-login      # Verify credentials with Lexyta LMS
  python run.py --test-ai         # Verify Gemini AI connection & solving
"""

import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.cli.main import run_cli

if __name__ == "__main__":
    run_cli()
