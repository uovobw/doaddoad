from doaddoad import DoadDoad
from Tweet import Tweet
import pickle
from nose.plugins.skip import Skip, SkipTest

def test_tweet_creation():
	twitter = pickle.load(open("test/data/singleTwitterStatus","r"))
	# create the tweet obj
	doaddoadTweet = Tweet(twitter)
	assert doaddoadTweet.status == twitter
	assert doaddoadTweet.get_language_code() == "en"


def test_load_state():
	d = DoadDoad()
	d.load_state()
	# assert it's a dict
	assert type(d.state) == dict
	# assert it's structure
	assert type(d.state.keys[0]) == int
	assert type(d.state.values[0]) == Tweet
