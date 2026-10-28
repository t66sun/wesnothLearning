"""The native log cap accepts a train-length game without launching Wesnoth."""
import unittest

from learning.common import VENDOR  # noqa: F401  binds vendor/arena on sys.path
import match


class NativeLogCapTests(unittest.TestCase):
    def test_16_mib_is_no_longer_a_failure(self):
        self.assertFalse(match.log_exceeded(16 * 1024 * 1024))

    def test_cap_is_eighty_mib(self):
        self.assertFalse(match.log_exceeded(80 * 1024 * 1024))
        self.assertTrue(match.log_exceeded(80 * 1024 * 1024 + 1))


if __name__ == '__main__':
    unittest.main()
