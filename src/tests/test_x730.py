import unittest
from . import pin_factory


class X730TestCase(unittest.TestCase):

    def setUp(self):
        pin_factory.reset()

    # TODO add tests for X730
    def test_hello_world(self):
        self.assertEqual("hello world!".upper(), "HELLO WORLD!")
