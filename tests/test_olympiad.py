"""
Unit Tests for Olympiad / Grand Quiz Integration
Tests parse_olympiad_input, OlympiadAPIClient, and Telegram bot /olympiad routing.
"""

import unittest
from unittest.mock import MagicMock, patch
from src.client.olympiad_api import parse_olympiad_input, OlympiadAPIClient
from src.bot.telegram_server import TelegramServer
from src.core.user_manager import UserManager
from src.core.access_control import AccessController


class TestOlympiadParser(unittest.TestCase):
    def test_parse_full_url_with_access_code(self):
        url = "https://olympiad.lexyta.com/8uicOlC454?access_code=QsjLttvz"
        parsed = parse_olympiad_input(url)
        self.assertEqual(parsed["slug"], "8uicOlC454")
        self.assertEqual(parsed["access_code"], "QsjLttvz")
        self.assertIsNone(parsed["invitation_code"])
        self.assertIsNone(parsed["key"])

    def test_parse_full_url_with_invitation_code(self):
        url = "https://olympiad.lexyta.com/8uicOlC454?invitation_code=INVITE_TOKEN_XYZ"
        parsed = parse_olympiad_input(url)
        self.assertEqual(parsed["slug"], "8uicOlC454")
        self.assertIsNone(parsed["access_code"])
        self.assertEqual(parsed["invitation_code"], "INVITE_TOKEN_XYZ")
        self.assertIsNone(parsed["key"])

    def test_parse_url_with_token_param(self):
        url = "https://olympiad.lexyta.com/my-slug-123?token=MY_TOKEN"
        parsed = parse_olympiad_input(url)
        self.assertEqual(parsed["slug"], "my-slug-123")
        self.assertEqual(parsed["invitation_code"], "MY_TOKEN")

    def test_parse_url_with_student_key(self):
        text = "https://olympiad.lexyta.com/8uicOlC454 key=STUDENT_KEY_99"
        parsed = parse_olympiad_input(text)
        self.assertEqual(parsed["slug"], "8uicOlC454")
        self.assertEqual(parsed["key"], "STUDENT_KEY_99")

    def test_parse_bare_slug(self):
        text = "8uicOlC454"
        parsed = parse_olympiad_input(text)
        self.assertEqual(parsed["slug"], "8uicOlC454")
        self.assertIsNone(parsed["access_code"])
        self.assertIsNone(parsed["invitation_code"])


class TestOlympiadAPIClient(unittest.TestCase):
    def setUp(self):
        self.client = OlympiadAPIClient(email="teststudent@gmail.com")

    @patch("requests.Session.post")
    def test_join_by_access_code_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        result = self.client.join_by_access_code("8uicOlC454", "QsjLttvz")
        self.assertTrue(result)
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn("https://olympiad.lexyta.com/api/olympiads/8uicOlC454/join", args[0])
        self.assertEqual(kwargs["json"], {"access_code": "QsjLttvz", "email": "teststudent@gmail.com"})

    @patch("requests.Session.get")
    def test_auth_with_token_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "std_1", "email": "teststudent@gmail.com"}
        mock_get.return_value = mock_resp

        result = self.client.auth_with_token("8uicOlC454", "TOKEN_ABC")
        self.assertTrue(result)
        mock_get.assert_called()
        self.assertEqual(self.client.current_slug, "8uicOlC454")

    @patch("requests.Session.post")
    def test_submit_attempt_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        answers = {"q1": "opt_a", "q2": "opt_b"}
        result = self.client.submit_attempt("8uicOlC454", answers)
        self.assertTrue(result)
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn("https://olympiad.lexyta.com/api/olympiads/8uicOlC454/me/attempt/submit", args[0])
        self.assertEqual(kwargs["json"], answers)


class TestTelegramOlympiadRouting(unittest.TestCase):
    def setUp(self):
        self.user_manager = MagicMock(spec=UserManager)
        self.access_controller = MagicMock(spec=AccessController)
        self.access_controller.is_allowed.return_value = True

        self.server = TelegramServer(
            bot_token="TEST_BOT_TOKEN",
            user_manager=self.user_manager,
            access_controller=self.access_controller
        )
        self.server.send_message = MagicMock(return_value=True)

    def test_olympiad_help_shown_when_no_args(self):
        self.user_manager.get_user.return_value = {"email": "test@gmail.com"}
        self.server.handle_olympiad_entry(123456, "/olympiad")
        self.server.send_message.assert_called_once()
        msg = self.server.send_message.call_args[0][1]
        self.assertIn("Grand Quiz & Olympiad", msg)

    @patch("src.client.olympiad_api.OlympiadAPIClient.join_by_access_code")
    @patch("src.client.olympiad_api.OlympiadAPIClient.get_base_info")
    def test_olympiad_access_code_triggers_join(self, mock_base, mock_join):
        self.user_manager.get_user.return_value = {"email": "test@gmail.com"}
        mock_base.return_value = {"name": "Midterm Olympiad"}
        mock_join.return_value = True

        self.server.handle_olympiad_entry(123456, "/olympiad https://olympiad.lexyta.com/8uicOlC454?access_code=QsjLttvz")
        mock_join.assert_called_once_with("8uicOlC454", "QsjLttvz")
        self.server.send_message.assert_called()
        last_msg = self.server.send_message.call_args[0][1]
        self.assertIn("Access Code Verified", last_msg)


if __name__ == "__main__":
    unittest.main()
