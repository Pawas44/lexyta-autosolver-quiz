import unittest
from src.core.access_control import AccessController

class TestAccessControl(unittest.TestCase):
    def test_parse_lines(self):
        controller = AccessController(admin_chat_id=8224782152)
        raw = """
        # Test Whitelist
        8224782152 # Admin
        1234567890
        
        987654321
        # Disabled
        # 111222333
        invalid_text
        """
        parsed = controller._parse_lines(raw)
        self.assertIn(8224782152, parsed)
        self.assertIn(1234567890, parsed)
        self.assertIn(987654321, parsed)
        self.assertNotIn(111222333, parsed)

    def test_is_allowed(self):
        controller = AccessController(admin_chat_id=8224782152)
        controller._cached_ids = {8224782152, 999888777}
        controller._last_fetch_time = 9999999999.0  # prevent auto-refresh in test

        self.assertTrue(controller.is_allowed(8224782152))
        self.assertTrue(controller.is_allowed("8224782152"))
        self.assertTrue(controller.is_allowed(999888777))
        self.assertFalse(controller.is_allowed(12345))
        self.assertFalse(controller.is_allowed("str_invalid"))

if __name__ == "__main__":
    unittest.main()
