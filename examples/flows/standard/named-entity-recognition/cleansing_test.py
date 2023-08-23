import unittest

from cleansing import cleansing


class CleansingTest(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(cleansing("a, b, c"), ["a", "b", "c"])
        self.assertEqual(cleansing("a, b, (425)137-98-25, "), ["a", "b", "(425)137-98-25"])
        self.assertEqual(cleansing("a, b, F. Scott Fitzgerald.,  d"), ["a", "b", "F. Scott Fitzgerald", "d"])
        self.assertEqual(cleansing("a, b, c,  None., "), ["a", "b", "c", "None"])
        self.assertEqual(cleansing(",,"), [])
        self.assertEqual(cleansing(""), [])
