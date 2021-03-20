import random
import time
import unittest

import twitter
from doaddoad import DoadDoad, Tweet


class DoaddoadStateTest(unittest.TestCase):
    def setUp(self):
        self.d = DoadDoad()

    def _add_tweet(self, text):
        created_at = time.time()
        id = random.randint(0, int(created_at))
        self.d.state[id] = Tweet(
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
