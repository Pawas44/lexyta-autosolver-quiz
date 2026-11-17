"""
Unit test for Lexyta LMS API Client.
"""

import unittest
from src.core.config import AppConfig
from src.client.lexyta_api import LexytaAPIClient

class TestLexytaClient(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig.load()
        self.client = LexytaAPIClient(self.config.email, self.config.password)

    def test_authentication_and_profile(self):
        success = self.client.signin()
        self.assertTrue(success, "Sign in should succeed with valid credentials")
        profile = self.client.get_profile()
        self.assertIsNotNone(profile)
        self.assertEqual(profile.get("email"), self.config.email)

    def test_enrolled_programs(self):
        self.client.signin()
        programs = self.client.get_enrolled_programs()
        self.assertIsInstance(programs, list)
        self.assertGreater(len(programs), 0, "Student should have at least 1 enrolled program")

if __name__ == "__main__":
    unittest.main()
