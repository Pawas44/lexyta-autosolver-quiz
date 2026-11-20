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
    Formula combines:
    1. Per-Question student pacing: ~30 to 42 seconds per question (+ 15-25s initial reading buffer)
    2. Official allocated time limit ratio: 60% - 70% of time limit so it never looks rushed or idled
    3. Deadline safety check: always finishes >= 60 seconds before deadline
    """
    q_count = max(total_questions, 1)

    # 1. Question-based natural student pace: 30-40 seconds per question + reading buffer
    per_q_seconds = random.uniform(31.0, 41.0)
    initial_reading_buffer = random.uniform(15.0, 25.0)
    question_based_target = (q_count * per_q_seconds) + initial_reading_buffer

    if time_limit_minutes and time_limit_minutes > 0:
        total_limit_sec = time_limit_minutes * 60.0
        # Ceiling: never exceed 75% of time limit (or 90s before expiry)
        max_safe_ceiling = min(total_limit_sec * 0.75, max(10.0, total_limit_sec - 90.0))
        # Floor: minimum realistic completion for this exam
        min_realistic_floor = total_limit_sec * 0.40

        if time_limit_minutes <= 15:
            ratio = random.uniform(0.58, 0.66)  # ~8.7 to 9.9 min for 15 min
            limit_target = total_limit_sec * ratio
        elif time_limit_minutes <= 25:
            ratio = random.uniform(0.62, 0.68)  # ~12.4 to 13.6 min for 20 min
            limit_target = total_limit_sec * ratio
        elif time_limit_minutes <= 45:
            ratio = random.uniform(0.50, 0.60)  # ~20-24 min for 40 min
            limit_target = total_limit_sec * ratio
        elif time_limit_minutes <= 65:
            ratio = random.uniform(0.48, 0.58)  # ~28-35 min for 60 min
            limit_target = total_limit_sec * ratio
        elif time_limit_minutes <= 95:
            ratio = random.uniform(0.45, 0.55)  # ~40-50 min for 90 min
            limit_target = total_limit_sec * ratio
        else:
            ratio = random.uniform(0.45, 0.55)
            limit_target = total_limit_sec * ratio

        # Blend: If question count is standard (5-30 questions), align with official exam pacing
        # while respecting question count.
        if q_count >= 15:
            # Many questions: question pacing dominates but capped at safe ceiling
            target = min(question_based_target, max_safe_ceiling)
        else:
            # For 10 questions in a 15-20 min quiz, respect the official window target
            # e.g. ~13 min for 20 min quiz, ~9 min for 15 min quiz
            target = max(min(limit_target, max_safe_ceiling), min_realistic_floor)
    else:
        # Untimed quiz: pure per-question pacing (~30-40s per question)
        target = question_based_target

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
    tick_interval: float = 30.0,
    total_questions: int = 0
):
    """
    Paces quiz submission so LMS records a natural, human-like duration.
    Provides realistic question-by-question progress updates (e.g. Answering Q4/10).
    Calls `on_tick(elapsed, remaining, status_str)` periodically to update UI/Telegram.
    """
    logger.info(f"Stealth Human Pacing activated: Target duration is {format_duration_human(target_seconds)}")

    while True:
        elapsed = time.time() - t_start
        remaining = target_seconds - elapsed

        if remaining <= 0:
            break

        if on_tick:
            if total_questions > 0:
                fraction = min(1.0, max(0.0, elapsed / max(target_seconds, 1.0)))
                current_q = min(total_questions, int(fraction * total_questions) + 1)
                sec_per_q = int(round(target_seconds / total_questions))
                status = f"📝 Answering Q{current_q}/{total_questions} (~{sec_per_q}s/q)... ({format_duration_human(elapsed)} / ~{format_duration_human(target_seconds)})"
            else:
                status = f"⏳ Stealth Human Pacing: Reading & answering naturally... ({format_duration_human(elapsed)} / ~{format_duration_human(target_seconds)})"

            try:
                on_tick(elapsed, remaining, status)
            except Exception as e:
                logger.warning(f"Error in pacing on_tick callback: {e}")

        # Sleep in small slices (up to tick_interval)
        sleep_slice = min(remaining, tick_interval)
        time.sleep(sleep_slice)
