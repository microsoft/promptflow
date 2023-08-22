import unittest

from match import is_match


class IsMatchTest(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(is_match(["a", "b"], ["B", "a"], True, True, False), True)
        self.assertEqual(is_match(["a", "b"], ["B", "a"], True, False, False), False)
        self.assertEqual(is_match(["a", "b"], ["B", "a"], False, True, False), False)
        self.assertEqual(is_match(["a", "b"], ["B", "a"], False, False, True), False)
        self.assertEqual(is_match(["a", "b"], ["a", "b"], False, False, False), True)
        self.assertEqual(is_match(["a", "b"], ["a", "b", "c"], True, False, True), True)
