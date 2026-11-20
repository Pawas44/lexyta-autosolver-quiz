import unittest
from unittest.mock import MagicMock, patch
from src.core.user_manager import UserManager
from src.bot.telegram_server import TelegramServer

class TestTelegramControls(unittest.TestCase):
    def setUp(self):
        self.user_manager = UserManager(file_path="data/test_controls_state.json")
        self.user_manager.users = {
            "12345": {
                "email": "test@student.com",
                "student_name": "Test Student",
                "program_name": "B.Tech CSE",
                "is_active": True,
                "auto_solve": True,
                "solved_quizzes": [],
                "notified_quizzes": [],
                "notified_assignments": []
            }
        }
        self.server = TelegramServer(bot_token="123456:FAKE_TOKEN_FOR_TEST", user_manager=self.user_manager)
        self.server.access_controller = MagicMock()
        self.server.access_controller.is_allowed.return_value = True

    def test_autosolve_toggle_in_user_manager(self):
        self.assertTrue(self.user_manager.get_user(12345).get("auto_solve"))
        self.user_manager.set_user_autosolve(12345, False)
        self.assertFalse(self.user_manager.get_user(12345).get("auto_solve"))
        self.user_manager.set_user_autosolve(12345, True)
        self.assertTrue(self.user_manager.get_user(12345).get("auto_solve"))

    def test_control_keyboard_active_and_autosolve(self):
        kb = self.server._get_control_keyboard(12345)
        buttons = kb.get("inline_keyboard", [])
        row1_texts = [btn["text"] for btn in buttons[0]]
        self.assertIn("🛑 Stop 24/7 Bot", row1_texts)
        self.assertIn("⚡ Auto-Solve: ON", row1_texts)

        # Switch off
        self.user_manager.set_user_active(12345, False)
        self.user_manager.set_user_autosolve(12345, False)
        kb2 = self.server._get_control_keyboard(12345)
        row1_texts2 = [btn["text"] for btn in kb2.get("inline_keyboard", [])[0]]
        self.assertIn("▶️ Resume 24/7 Bot", row1_texts2)
        self.assertIn("⏸️ Auto-Solve: OFF", row1_texts2)

    @patch.object(TelegramServer, "answer_callback_query")
    @patch.object(TelegramServer, "edit_message")
    def test_handle_callback_query_stop_and_resume(self, mock_edit, mock_answer):
        # Stop button clicked
        query_stop = {
            "id": "q1",
            "data": "btn_stop",
            "message": {"message_id": 101, "chat": {"id": 12345}},
            "from": {"id": 12345}
        }
        self.server.handle_callback_query(query_stop)
        self.assertFalse(self.user_manager.get_user(12345).get("is_active"))
        mock_answer.assert_called_with("q1", "🛑 24/7 Bot Stopped!")

        # Resume button clicked
        query_resume = {
            "id": "q2",
            "data": "btn_resume",
            "message": {"message_id": 101, "chat": {"id": 12345}},
            "from": {"id": 12345}
        }
        self.server.handle_callback_query(query_resume)
        self.assertTrue(self.user_manager.get_user(12345).get("is_active"))
        mock_answer.assert_called_with("q2", "▶️ 24/7 Bot Resumed!")

    @patch.object(TelegramServer, "answer_callback_query")
    @patch.object(TelegramServer, "edit_message")
    def test_handle_callback_query_autosolve(self, mock_edit, mock_answer):
        # Auto-solve off button clicked
        query_off = {
            "id": "q3",
            "data": "btn_autosolve_off",
            "message": {"message_id": 101, "chat": {"id": 12345}},
            "from": {"id": 12345}
        }
        self.server.handle_callback_query(query_off)
        self.assertFalse(self.user_manager.get_user(12345).get("auto_solve"))
        mock_answer.assert_called_with("q3", "⏸️ Auto-Solve Disabled (Notify Only)")

        # Auto-solve on button clicked
        query_on = {
            "id": "q4",
            "data": "btn_autosolve_on",
            "message": {"message_id": 101, "chat": {"id": 12345}},
            "from": {"id": 12345}
        }
        self.server.handle_callback_query(query_on)
        self.assertTrue(self.user_manager.get_user(12345).get("auto_solve"))
        mock_answer.assert_called_with("q4", "⚡ Auto-Solve Enabled (Full Auto)")

    @patch.object(TelegramServer, "send_message")
    def test_commands_stop_resume_autosolve(self, mock_send):
        # /stop command
        self.server.handle_message({"chat": {"id": 12345}, "text": "/stop"})
        self.assertFalse(self.user_manager.get_user(12345).get("is_active"))

        # /resume command
        self.server.handle_message({"chat": {"id": 12345}, "text": "/resume"})
        self.assertTrue(self.user_manager.get_user(12345).get("is_active"))

        # /autosolve off
        self.server.handle_message({"chat": {"id": 12345}, "text": "/autosolve off"})
        self.assertFalse(self.user_manager.get_user(12345).get("auto_solve"))

        # /autosolve on
        self.server.handle_message({"chat": {"id": 12345}, "text": "/autosolve on"})
        self.assertTrue(self.user_manager.get_user(12345).get("auto_solve"))

    def test_solve_lock_acquire_and_release(self):
        self.assertFalse(self.user_manager.is_user_solving(12345))
        self.assertTrue(self.user_manager.acquire_solve_lock(12345))
        self.assertTrue(self.user_manager.is_user_solving(12345))
        # Second acquire must fail
        self.assertFalse(self.user_manager.acquire_solve_lock(12345))
        # Release lock
        self.user_manager.release_solve_lock(12345)
        self.assertFalse(self.user_manager.is_user_solving(12345))
        # Can acquire again
        self.assertTrue(self.user_manager.acquire_solve_lock(12345))
        self.user_manager.release_solve_lock(12345)

    @patch.object(TelegramServer, "send_message")
    def test_duplicate_solve_command_blocked(self, mock_send):
        self.user_manager.acquire_solve_lock(12345)
        self.server.handle_message({"chat": {"id": 12345}, "text": "/solve"})
        mock_send.assert_called_with(
            12345,
            "⚠️ <b>Quiz solving already chal raha hai!</b>\n\nUpar progress message dekhein. Jab tak wo pura na ho tab tak dobara command na bhejein."
        )
        self.user_manager.release_solve_lock(12345)

    def tearDown(self):
        import os
        if os.path.exists("data/test_controls_state.json"):
            try:
                os.remove("data/test_controls_state.json")
            except Exception:
                pass

if __name__ == "__main__":
    unittest.main()
