"""
Unit and Integration Tests for Lecture Notes, PPT & Material Downloader.
"""

import unittest
from unittest.mock import MagicMock, patch
from src.core.config import AppConfig
from src.client.lexyta_api import LexytaAPIClient
from src.bot.telegram_server import TelegramServer, format_file_size

class TestMaterials(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig.load()
        self.client = LexytaAPIClient(self.config.email, self.config.password)

    def test_file_size_formatter(self):
        self.assertEqual(format_file_size(500), "500 B")
        self.assertEqual(format_file_size(2048), "2.0 KB")
        self.assertEqual(format_file_size(2607104), "2.5 MB")
        self.assertEqual(format_file_size(0), "Unknown size")

    def test_fetch_resources_and_topics(self):
        self.assertTrue(self.client.signin())
        programs = self.client.get_enrolled_programs()
        self.assertGreater(len(programs), 0)
        classes = self.client.get_program_classes(programs[0]["id"])
        self.assertGreater(len(classes), 0)

        # Test fetching resources
        first_cls_id = classes[0]["id"]
        resources = self.client.get_class_resources(first_cls_id)
        self.assertIsInstance(resources, list)

        # Test fetching topics if course exists
        course = classes[0].get("course")
        if course and course.get("id"):
            topics = self.client.get_course_topics(course["id"])
            self.assertIsInstance(topics, list)

    def test_file_download_api(self):
        self.assertTrue(self.client.signin())
        # Known test file on LMS: PRACTICAL LIST bca 3rd1.pdf
        fid = "28581129-74c8-48fa-b569-14b279a37b0a"
        url = self.client.get_file_download_url(fid)
        self.assertIsNotNone(url)
        self.assertTrue(url.startswith("https://"))

        raw = self.client.download_file_bytes(fid)
        self.assertIsNotNone(raw)
        self.assertGreater(len(raw), 1000)

    @patch("requests.post")
    def test_telegram_send_document(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True}
        mock_post.return_value = mock_resp

        server = TelegramServer(bot_token="123456:FAKE_TOKEN")
        sent = server.send_document(12345678, b"%PDF-mock-bytes", "test.pdf", "Caption text")
        self.assertTrue(sent)
        self.assertTrue(mock_post.called)

if __name__ == "__main__":
    unittest.main()
