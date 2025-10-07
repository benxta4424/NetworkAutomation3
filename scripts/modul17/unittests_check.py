import unittest

from modul17.my_functions import area


class TestCase(unittest.TestCase):

    def test_area(self):
        self.assertEqual(12, area(3, 4))


    def test_invalid_area(self):
        self.assertRaises(ValueError, area, -3, 4)
