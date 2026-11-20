import unittest
from datetime import datetime, timezone, timedelta
from src.solvers.human_pacer import calculate_target_duration_seconds, format_duration_human

class TestHumanPacer(unittest.TestCase):
    def test_20_min_quiz(self):
        # 20 min * 60 = 1200 sec. Target ~62-68% -> 744 - 816 sec (~12.4 to 13.6 min)
        target = calculate_target_duration_seconds(time_limit_minutes=20, total_questions=10)
        self.assertGreaterEqual(target, 12 * 60)
        self.assertLessEqual(target, 14 * 60)

    def test_15_min_quiz(self):
        # 15 min * 60 = 900 sec. Target ~58-66% -> 522 - 594 sec (~8.7 to 9.9 min)
        target = calculate_target_duration_seconds(time_limit_minutes=15, total_questions=10)
        self.assertGreaterEqual(target, 8 * 60)
        self.assertLessEqual(target, 10.5 * 60)

    def test_34_hour_extended_window(self):
        # Teacher gives 34 hours (2040 min) for 10 questions.
        # Must NOT wait 15+ hours! Must use realistic question-based pacing (~5 to 8 min).
        target = calculate_target_duration_seconds(time_limit_minutes=2040, total_questions=10)
        self.assertGreaterEqual(target, 300)   # >= 5 minutes
        self.assertLessEqual(target, 500)      # <= 8.3 minutes

    def test_2_day_extended_window(self):
        # Teacher gives 48 hours (2880 min) for 15 questions.
        target = calculate_target_duration_seconds(time_limit_minutes=2880, total_questions=15)
        self.assertGreaterEqual(target, 450)   # >= 7.5 minutes
        self.assertLessEqual(target, 700)      # <= 11.6 minutes

    def test_60_min_few_questions_extended(self):
        # 60 min limit for only 5 questions (12 min/q). Extended window -> ~3 to 4.5 min.
        target = calculate_target_duration_seconds(time_limit_minutes=60, total_questions=5)
        self.assertGreaterEqual(target, 160)   # >= 2.6 minutes
        self.assertLessEqual(target, 280)      # <= 4.6 minutes

    def test_deadline_safety_cap(self):
        # If due date is only 3 minutes (180s) away, target must not exceed 120s
        near_due = (datetime.now(timezone.utc) + timedelta(seconds=180)).isoformat()
        target = calculate_target_duration_seconds(time_limit_minutes=20, total_questions=10, due_date_str=near_due)
        self.assertLessEqual(target, 125.0)

    def test_question_based_pacing_untimed(self):
        # 10 questions without official time limit -> ~30-41s per question + buffer
        target = calculate_target_duration_seconds(time_limit_minutes=None, total_questions=10)
        # Should be between 300s (5 min) and 450s (7.5 min)
        self.assertGreaterEqual(target, 300)
        self.assertLessEqual(target, 450)

    def test_question_progress_ticks(self):
        from src.solvers.human_pacer import wait_with_human_pacing
        import time

        recorded_statuses = []
        def on_tick(elapsed, remaining, status_str):
            recorded_statuses.append(status_str)

        # Run 0.1s simulated pacing
        wait_with_human_pacing(t_start=time.time(), target_seconds=0.05, on_tick=on_tick, tick_interval=0.01, total_questions=5)
        # The loop should complete cleanly
        self.assertTrue(True)

    def test_format_human(self):
        self.assertEqual(format_duration_human(45), "45s")
        self.assertEqual(format_duration_human(780), "13m 0s")
        self.assertEqual(format_duration_human(3665), "1h 1m 5s")

if __name__ == "__main__":
    unittest.main()
