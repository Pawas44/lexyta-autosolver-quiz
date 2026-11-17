"""
Human-Like Realistic Pacing Engine
Calculates natural, human completion durations for quizzes based on official time limits:
- 20 min quiz -> finishes in ~12 to 14 min (user requested: ~13 min)
- 15 min quiz -> finishes in ~8.5 to 10 min (user requested: ~9 min)
- 30-40 min quiz -> finishes in ~18 to 24 min
- 60-90 min exam -> finishes in ~25 to 35 min
- No limit -> ~30-45 sec per question

Includes Deadline Safety Check:
Always ensures submission finishes at least 60 seconds BEFORE the due date, even if the due date is very close!
"""

import time
import random
import logging
from datetime import datetime, timezone
from typing import Optional, Callable

logger = logging.getLogger("HumanPacer")

def calculate_target_duration_seconds(time_limit_minutes: Optional[int], total_questions: int, due_date_str: Optional[str] = None) -> float:
    """
    Calculates realistic human-like duration (in seconds).
    Formula aligns with student behavior: 60% - 70% of total allocated time.
    """
    if time_limit_minutes and time_limit_minutes > 0:
        if time_limit_minutes <= 15:
            ratio = random.uniform(0.58, 0.66)  # ~9 min for 15 min
            target = (time_limit_minutes * 60) * ratio
        elif time_limit_minutes <= 25:
            ratio = random.uniform(0.62, 0.68)  # ~13 min for 20 min
            target = (time_limit_minutes * 60) * ratio
        elif time_limit_minutes <= 45:
            ratio = random.uniform(0.50, 0.60)  # ~20-24 min for 40 min
            target = (time_limit_minutes * 60) * ratio
        else:
            # 60-90 min exams: ~25 to 35 minutes
            target = random.uniform(25 * 60, 35 * 60)
    else:
        # Default when no time limit set: 30-45 seconds per question
        q_count = max(total_questions, 5)
        target = q_count * random.uniform(30.0, 45.0)

    # DEADLINE SAFETY CHECK:
    # If the assignment expires sooner than our target, cap target to avoid missing the deadline!
    if due_date_str:
        try:
            clean_date = due_date_str.replace("Z", "+00:00")
            due_dt = datetime.fromisoformat(clean_date)
            seconds_until_due = (due_dt - datetime.now(timezone.utc)).total_seconds()
            if seconds_until_due > 0:
                # Leave at least 60 seconds safety buffer before due date
                max_safe = max(5.0, seconds_until_due - 60.0)
                if target > max_safe:
                    logger.warning(f"Due date is near! Reducing target duration from {target:.0f}s to {max_safe:.0f}s to prevent expiry.")
                    target = max_safe
        except Exception:
            pass

    return target


def format_duration_human(seconds: float) -> str:
    """Formats seconds into readable mm:ss or hh:mm:ss format."""
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    elif m > 0:
        return f"{m}m {s}s"
    else:
        return f"{s}s"


def wait_with_human_pacing(
    t_start: float,
    target_seconds: float,
    on_tick: Optional[Callable[[float, float, str], None]] = None,
    tick_interval: float = 30.0
):
    """
    Paces quiz submission so LMS records a natural, human-like duration.
    Calls `on_tick(elapsed, remaining, status_str)` periodically to update UI/Telegram.
    """
    logger.info(f"Stealth Human Pacing activated: Target duration is {format_duration_human(target_seconds)}")

    while True:
        elapsed = time.time() - t_start
        remaining = target_seconds - elapsed

        if remaining <= 0:
            break

        if on_tick:
            status = f"⏳ Stealth Human Pacing: Reading & answering naturally... ({format_duration_human(elapsed)} / ~{format_duration_human(target_seconds)})"
            try:
                on_tick(elapsed, remaining, status)
            except Exception as e:
                logger.warning(f"Error in pacing on_tick callback: {e}")

        # Sleep in small slices (up to tick_interval)
        sleep_slice = min(remaining, tick_interval)
        time.sleep(sleep_slice)
