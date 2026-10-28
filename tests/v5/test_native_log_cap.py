"""The native log cap accepts a train-length game without launching Wesnoth."""
import unittest

from learning.common import VENDOR  # noqa: F401  binds vendor/arena on sys.path
import match


class NativeLogCapTests(unittest.TestCase):
    def test_a_game_past_the_old_limit_no_longer_fails(self):
        self.assertFalse(match.log_exceeded(16 * 1024 * 1024 + 1))

    def test_cap_is_eighty_mib(self):
        self.assertFalse(match.log_exceeded(80 * 1024 * 1024))
        self.assertTrue(match.log_exceeded(80 * 1024 * 1024 + 1))

    def test_captured_frames_do_not_count_against_the_cap(self):
        prefix = 'ARENA2 0123456789abcdef '
        stock = prefix + 'STOCK {"kind": "ROW", "row": {}}\n'
        learn = prefix + 'LEARN {"id": 1}\n'
        chatter = prefix + 'TURN {"side": 1, "turn": 2}\n'
        self.assertEqual(match.log_weight(stock, prefix), 0)
        self.assertEqual(match.log_weight(learn, prefix), 0)
        self.assertEqual(match.log_weight(chatter, prefix), len(chatter))


if __name__ == '__main__':
    unittest.main()
