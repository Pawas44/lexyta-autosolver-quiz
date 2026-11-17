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

    def test_deadline_safety_cap(self):
        # If due date is only 3 minutes (180s) away, target must not exceed 120s
        near_due = (datetime.now(timezone.utc) + timedelta(seconds=180)).isoformat()
        target = calculate_target_duration_seconds(time_limit_minutes=20, total_questions=10, due_date_str=near_due)
        self.assertLessEqual(target, 125.0)

    def test_format_human(self):
        self.assertEqual(format_duration_human(45), "45s")
        self.assertEqual(format_duration_human(780), "13m 0s")
        self.assertEqual(format_duration_human(3665), "1h 1m 5s")

if __name__ == "__main__":
    unittest.main()
