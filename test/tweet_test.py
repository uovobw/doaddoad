from doaddoad import Tweet
import pickle

def test_tweet_creation():
	twitter = pickle.load(open("test/data/singleTwitterStatus","r"))
	# create the tweet obj
	doaddoadTweet = Tweet(twitter)
	assert doaddoadTweet.status == twitter
	assert doaddoadTweet.get_language_code() == "en"
	
