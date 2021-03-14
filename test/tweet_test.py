import unittest

from doaddoad import DoadDoad
from Tweet import Tweet


class DummyStatus(object):
    def __init__(self, text):
        self.text = text


class TweetTest(unittest.TestCase):
    def test_tweet_creation(self):
      doaddoadTweet = Tweet(DummyStatus("This is an english sentence."))
      self.assertEqual(doaddoadTweet.get_language_code(), "en")
