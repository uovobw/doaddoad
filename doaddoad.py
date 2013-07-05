#!/usr/bin/python

import cPickle
import logging
import optparse
import os
import random
import re
import subprocess
import sys
import time
import cStringIO as StringIO

from twitter import TwitterError
from Tweet import Tweet
# you'll need at least the git version e572f2ff4
# https://github.com/bear/python-twitter
import twitter
import cld
# you'll need at least the git version 9f666cda
# https://github.com/maraujop/requests-oauth
import oauth_hook
import requests

import secrets

TWEET_MAXLENGTH = 140

log = logging.getLogger(__name__)


class DoadDoadError(Exception):
    pass


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

        log.debug("loading state from %s", self.state_file)
        with open(self.state_file, "r") as state_file:
            self.state = cPickle.load(state_file)

    # XXX make load/save state context managers
    def save_state(self, limit=5000):
        """Persist the state to self.state_file, using only the newest limit tweets."""
        self._trim_state(limit)

        log.debug("saving state to %s", self.state_file)
        with open(self.state_file, "w") as state_file:
            cPickle.dump(self.state, state_file, -1)

    # XXX generating a lot of tweets is not efficient because we're forking dadadodo
    # each time
    def generate_tweet(self, language=None):
        """Generate a random tweet from the given state, consider only tweets in the given language."""

        def _dadadodo_input(language=None):
            """Generate input for dadadodo, munge the state into something usable."""
            shuffled_ids = self.state.keys()
            random.shuffle(shuffled_ids)
            for tweet_id in shuffled_ids:
                tweet = self.state[tweet_id]
                if language and language != tweet.get_language_code():
                    continue
                text = tweet.status.text.encode("ascii", "ignore")
                text = re.sub(r'\s+', ' ', text)
                yield text

        def _extract_tweet(text):
            """Fix output from dadadodo into a usable tweet."""
            log.debug("extracting a tweet from %s", repr(text))
            text = text.replace("\t", " ").replace("\n", " ").strip()
            text = re.sub(" +", " ", text)

            if len(text) > TWEET_MAXLENGTH:
                log.debug("trimming '%s' from %d to %d", text, len(text), TWEET_MAXLENGTH)
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
        #log.debug("text from dadadodo '%s'", repr(result))

        generated_tweet = _extract_tweet(result)
        log.debug("extracted tweet %s", repr(generated_tweet))

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
        log.debug("fetching followers to followback")
        followers = set([ x.id for x in twitter.GetFollowers() ])
        log.debug("fetching friends to followback")
        following = set([ x.id for x in twitter.GetFriends() ])

        for user_id in followers - following:
            try:
                new_user = twitter.CreateFriendship(user_id)
                log.info("followed back %s", new_user)
            except TwitterError as e:
                log.warn("error in following user id %s: %s", user_id, e)

    def _change_profile_picture(self, twitter, probability):
        """Randomly change the profile picture with one of the followers"""
        if (random.random() * 100) >= probability:
            return

        api_url = "%s/account/update_profile_image.json" % twitter.base_url

        follower_clone = [ user for user in twitter.GetFollowers() ]
        follower_clone = random.choice(follower_clone)

        if not follower_clone:
            return

        profile_image_url = follower_clone.GetProfileImageUrl()
        screen_name = follower_clone.GetScreenName()

        hook = oauth_hook.OAuthHook(access_token=twitter._access_token_key,
                            access_token_secret=twitter._access_token_secret,
                            consumer_key=twitter._consumer_key,
                            consumer_secret=twitter._consumer_secret,
                            header_auth=True)

        client = requests.session(hooks={'pre_request': hook})
        log.debug("fetching new profile picture %s", profile_image_url)
        image_file = StringIO.StringIO(twitter._FetchUrl(profile_image_url))
        response = client.post(api_url, files={"image" : image_file})
        # abusing python-twitter internal API, checks if the response contains an error
        twitter._ParseAndCheckTwitter(response.content)
        log.info("changed profile picture with @%s's (%s)", screen_name, profile_image_url)

    def update(self, twitter, probability=33, maxupdates=0):
        """Update the state with new timelines from all followers.

           Additionally change the profile picture with probability with one from our followers."""
        self._followback(twitter)

        log.debug("fetching followers")
        followers = twitter.GetFollowers()
        if maxupdates > 0 and maxupdates > len(followers):
            log.info("limiting timeline fetching to %s", maxupdates)
            random.shuffle(followers)
            followers = followers[:maxupdates]

        for follower in followers:
            log.debug("fetching timeline for %s (@%s)" % (follower.name,
                follower.screen_name))
            self.add_timeline(twitter, follower.id)

        self._change_profile_picture(twitter, probability)

    def add_timeline(self, twitter, user, count=20):
        """Add the last count tweets from the specified user."""
        try:
            timeline = twitter.GetUserTimeline(user_id=user, count=count)
            # add all not-yet-seen tweets to the state which is keyed by tweet-id
            for tweet in timeline:
                if tweet.id not in self.state:
                    self._add_tweet(tweet)
        except TwitterError as e:
            if e.message == "Not authorized":
                log.info("Not authorized to get the timeline of the user")
            else:
                log.info(e)

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
    parser.add_option("-f", "--state-file", dest="state_file", default="doaddoad.state",
            metavar="FILE", help="load and save state from FILE (%default)")
    parser.add_option("-t", "--trim", dest="state_limit", default=5000,
            metavar="NUMBER", help="keep the last NUMBER tweets when saving state, 0 to disable (%default)")
    parser.add_option("-s", "--status", dest="usertweet", metavar="TEXT", help="post an arbitrary status to twitter")
    parser.add_option("-l", "--lang", dest="language", default=None, metavar="LANG",
            help="consider only tweets in language code LANG "
                 "e.g. 'en' (default: all tweets)")
    # this is done only when updating the state, but it isn't clear
    parser.add_option("-p", "--probability", dest="probability", default=33, metavar="NUMBER",
            help="probability of setting the profile to picture to one of the followers' (%default)")
    parser.add_option("-m", "--maxupdates", dest="maxupdates", default=0, metavar="NUMBER",
            help="limit the number of timelines to fetch, useful if hitting twitter's API limit (%default)")
    parser.add_option("-L", "--logfile", action="store", dest="logfile", metavar="FILENAME",
            help="write log to FILENAME")

    opts, args = parser.parse_args()

    logfd = sys.stdout
    if opts.logfile:
        logfd = open(opts.logfile, "a")

    logging.basicConfig(level=logging.INFO, stream=logfd, format="[%(asctime)-15s] %(message)s")
    if opts.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    twitter_api = twitter.Api(consumer_key=secrets.consumer_key,
            consumer_secret=secrets.consumer_secret,
            access_token_key=secrets.access_token_key,
            access_token_secret=secrets.access_token_secret)

    d = DoadDoad(state_file=opts.state_file)
    d.load_state()

    # update the state file with the timeline from our followers first
    # in case of an empty state this "primes" the state (if we've got any followers)
    if not opts.dry_run:
        if not os.path.exists(d.state_file) or \
                os.stat(d.state_file).st_mtime <= time.time() - opts.state_refresh:
            log.info("updating state file %s" % d.state_file)
            d.update(twitter_api, opts.probability, int(opts.maxupdates))
            d.save_state(limit=opts.state_limit)

    if opts.usertweet:
        tweet = opts.usertweet
    else:
        tweet = d.generate_tweet(opts.language)
        if not tweet:
            log.error("didn't get a tweet to post!")
            return 1

    log.info("updating timeline with %s" % repr(tweet))

    if not opts.dry_run:
        twitter_api.PostUpdate(tweet)

    rate_limit_status = twitter_api.GetRateLimitStatus()
    log.info("remaining API hits %s", rate_limit_status.get('remaining_hits', 'N/A'))


if __name__ == '__main__':
    logging.basicConfig()
    logging.error("this module should be imported")
    sys.exit(1)
