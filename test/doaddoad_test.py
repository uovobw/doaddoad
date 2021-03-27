import random
import time
import unittest

import twitter
import doaddoad


class DoaddoadStateTest(unittest.TestCase):
    def setUp(self):
        self.d = doaddoad.DoadDoad()

    def _add_tweet(self, text):
        created_at = time.time()
        id = random.randint(0, int(created_at))
        self.d.state[id] = doaddoad.Tweet(
            twitter.Status.NewFromJsonDict(
                {"id": id, "created_at": created_at, "text": text}
            )
        )

    def test_load_empty_state(self):
        self.d.load_state()
        assert self.d.state == {}

    def test_generate_tweet(self):
        self._add_tweet("lorem ipsum dolor sit amet")
        t = self.d.generate_tweet()
        assert len(t) > 10
        assert "  " not in t
        assert "\n" not in t

    def test_fix_rt(self):
        res = self.d._fix_rt("foo RT @bar")
        assert res == "RT @bar foo"

        res = self.d._fix_rt("foo bar")
        assert res == "foo bar"

    def test_extract_tweet(self):
        res = self.d._extract_tweet("foo \t   bar \n  baz\t\t meh \n\n")
        assert res == "foo bar baz meh"

        res = self.d._extract_tweet("a" * 666)
        assert res == "a" * doaddoad.TWEET_MAXLENGTH
