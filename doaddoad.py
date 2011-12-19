#!/usr/bin/python

import cPickle
import logging
import optparse
import os
from random import shuffle
import re
import subprocess
import sys
import time

import twitter
import cld

import secrets

TWEET_MAXLENGTH = 140

log = logging.getLogger(__name__)

class DoadDoadError(Exception):
    pass


# XXX make it more like a proxy for twitter.Status
class Tweet(object):
    """Wrap a twitter.Status object with language detection methods."""

    language_codes = [ x[1] for x in cld.LANGUAGES ]

    def __init__(self, status):
        self.status = status
        self.cld_result = None

        try:
            # topLanguageName, topLanguageCode, isReliable, textBytesFound, details
            self.cld_result = cld.detect(status.text.encode("ascii", "ignore"),
                                         isPlainText=True,
                                         includeExtendedLanguages=False)
        except UnicodeEncodeError, e:
            log.warn("language detection failed on %s" % repr(status.text))

    def get_language_code(self, reliable=True):
        if not self.cld_result: return None

        if reliable:
            return reliable == self.cld_result[2] and self.cld_result[1] or None

        return self.cld_result[1]


class DoadDoad(object):
    def __init__(self, state_file="doaddoad.state", dadadodo_bin="/usr/bin/dadadodo"):
        self.dadadodo_cmd = [dadadodo_bin]
        self.dadadodo_opts = ["-c", "1", "-"]

        # state is a dict tweet_id: Tweet object
        self.state = {}
        self.state_file = state_file

    def _run_dadadodo(self, input_string):
        dadadodo = subprocess.Popen(self.dadadodo_cmd + self.dadadodo_opts,
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE)
        out, err = dadadodo.communicate(input_string)

        return out

    def load_state(self):
        if not os.path.exists(self.state_file):
            return

        with open(self.state_file, "r") as state_file:
            self.state = cPickle.load(state_file)

    # XXX make load/save state context managers
    def save_state(self, limit=5000):
        """Persist the state to self.state_file, using only the newest limit tweets."""
        self._trim_state(limit)

        with open(self.state_file, "w") as state_file:
            cPickle.dump(self.state, state_file, -1)

    # XXX generating a lot of tweets is not efficient because we're forking dadadodo
    # each time
    def generate_tweet(self, language=None):
        """Generate a random tweet from the given state, consider only tweets in the given language."""

        def _dadadodo_input(language=None):
            """Generate input for dadadodo, munge the state into something usable."""
            shuffled_ids = self.state.keys()
            shuffle(shuffled_ids)
            for tweet_id in shuffled_ids:
                tweet = self.state[tweet_id]
                if language and language != tweet.get_language_code():
                    continue
                text = tweet.status.text.encode("ascii", "ignore")
                text = re.sub(r'\s+', ' ', text)
                yield text

        def _extract_tweet(text):
            """Fix output from dadadodo into a usable tweet."""
            log.debug("extracting a tweet from %s" % repr(text))
            text = text.replace("\t", " ").replace("\n", " ").strip()
            text = re.sub(" +", " ", text)

            if len(text) > TWEET_MAXLENGTH:
                log.debug("trimming '%s' from %d to %d" % (text, len(text), TWEET_MAXLENGTH))
                # trim to length and discard truncated words
                text = text[:TWEET_MAXLENGTH]
                text = text[:text.rindex(" ")]

            # if an RT is generated in the middle of a tweet, move RT at the
            # beginning and prepend whatever word was after that with @
            rt_find_re = re.compile(r"(?P<lead>^.*)([Rr][Tt]) +@?"
                                     "(?P<who>\S+) ?(?P<trail>.*)$")
            rt_match = rt_find_re.match(text)
            if rt_match:
                text = "RT @%s %s%s" % (rt_match.group('who'),
                                        rt_match.group('lead'),
                                        rt_match.group('trail'))

            return text

        if language and language not in Tweet.language_codes:
            raise DoadDoadError("language %s is not detectable" % repr(language))

        input_text = " ".join(_dadadodo_input(language))
        result = self._run_dadadodo(input_text)
        #log.debug("text from dadadodo '%s'" % repr(result))

        generated_tweet = _extract_tweet(result)
        log.debug("extracted tweet %s" % repr(generated_tweet))

        return generated_tweet

    def _trim_state(self, limit):
        if limit == 0: return

        # instead of fiddling with timestamps, assume there's a correlation
        # between tweet id and the time it has been posted.
        # Thus, sort the state and keep only the limit biggest ids
        for key in sorted(self.state)[:-limit]:
            del self.state[key]

    def _followback(self, twitter):
        """Follow back each of our followers."""
        followers = set([ x for x in twitter.GetFollowerIDs() ])
        following = set([ x for x in twitter.GetFriendIDs() ])

        for user_id in followers - following:
            new_user = twitter.CreateFriendship(user_id)
            log.info("followed back %s" % new_user)

    def update(self, twitter):
        """Update the state with new timelines from all followers."""
        self._followback(twitter)

        followers = twitter.GetFollowers()
        for follower in followers:
            log.debug("fetching timeline for %s (@%s)" % (follower.name,
                follower.screen_name))
            self.add_timeline(twitter, follower.id)

    def add_timeline(self, twitter, user, count=20):
        """Add the last count tweets from the specified user."""
        timeline = twitter.GetUserTimeline(id=user, count=count)

        # add all not-yet-seen tweets to the state which is keyed by tweet-id
        for tweet in timeline:
            if tweet.id not in self.state:
                self._add_tweet(tweet)

    def _add_tweet(self, tweet):
        # encapsulate twitter.Status into our own cld-aware Tweet
        tweet = Tweet(tweet)
        self.state[tweet.status.id] = tweet


# XXX interactive mode: generate tweets and selectively choose which ones to post
# XXX randomly reply to people which have replied to us?
def main():

    parser = optparse.OptionParser()
    parser.add_option("-n", "--dry-run", dest="dry_run", default=False,
            action="store_true", help="do not change the state, just print what would be done")
    parser.add_option("-d", "--debug", dest="debug", default=False,
            action="store_true", help="print debug information")
    parser.add_option("-r", "--refresh", dest="state_refresh", default=7200,
            metavar="SECONDS", help="refresh the state every SECONDS (%default)")
    parser.add_option("-t", "--trim", dest="state_limit", default=5000,
            metavar="NUMBER", help="keep the last NUMBER tweets when saving state, 0 to disable (%default)")
    parser.add_option("-l", "--lang", dest="language", default=None, metavar="LANG",
            help="consider only tweets in language code LANG "
                 "e.g. 'en' (default: all tweets)")
    opts, args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    if opts.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    twitter_api = twitter.Api(consumer_key=secrets.consumer_key,
            consumer_secret=secrets.consumer_secret,
            access_token_key=secrets.access_token_key,
            access_token_secret=secrets.access_token_secret)

    d = DoadDoad()
    d.load_state()

    tweet = d.generate_tweet(opts.language)
    if not tweet:
        logging.error("didn't get a tweet to post!")
        return 1

    logging.info("updating timeline with %s" % repr(tweet))

    if opts.dry_run:
        # everything below changes the state, just quit for now
        return 0

    twitter_api.PostUpdate(tweet)

    if not os.path.exists(d.state_file) or \
            os.stat(d.state_file).st_mtime <= time.time() - opts.state_refresh:
        logging.info("updating state file %s" % d.state_file)
        d.update(twitter_api)
        d.save_state(limit=opts.state_limit)


if __name__ == '__main__':
    sys.exit(main())
