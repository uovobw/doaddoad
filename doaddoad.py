#!/usr/bin/env python2.7

import cPickle as pickle
import os
import re
import subprocess
import sys
import time
import argparse

import twitter
import cld

import secrets

class DadaDodo(object):
	def __init__(self):

		parser = argparse.ArgumentParser(description='Process some integers.')
		parser.add_argument('-d',"--debug",dest='debug',action='store_true',default=False,help='enable debug mode (do not post to twitter,just print the generated tweet)')
		parser.add_argument("-l","--language",dest="language",action="store",default="en",help="select the two digit code of the language to use for tweets (en,it,de...)")
		parser.add_argument("-f","--file",dest="statefile",action="store",default="twitter.log",help="the	file to be used to store the state of the script bewteen runs")
		parser.add_argument("-t","--refreshtime",dest="refreshtime",action="store",default=7200,help="the time after which update the state")
		args = parser.parse_args()
		
		self.dadadodo = ["/usr/bin/dadadodo","-c","1","-"]
		self.thisUser = "doaddoad"
		self.twitterLog = args.statefile
		self.lang = args.language
		self.debug = args.debug
		self.refreshCacheTime = args.refreshtime

		self.consumer_key = secrets.consumer_key
		self.consumer_secret = secrets.consumer_secret
		self.access_token_key =	secrets.access_token_key
		self.access_token_secret = secrets.access_token_secret

		self.api = twitter.Api(consumer_key=self.consumer_key,
		                       consumer_secret=self.consumer_secret,
		                       access_token_key=self.access_token_key,
		                       access_token_secret=self.access_token_secret)
		self.user = None

		try:
			user = self.api.VerifyCredentials()
			self.user = user
		except twitter.TwitterError, e:
			print "ERROR in authenticating to twitter: %s" % e
			sys.exit(123)

		self.lang = "en"
		self.state = self.loadState()
		self.stateLimit = 15000


	def launch(self,strInput):
		dadadodo = subprocess.Popen(self.dadadodo,
		                            stdin=subprocess.PIPE,
		                            stderr=subprocess.PIPE,
		                            stdout=subprocess.PIPE)
		out, err = dadadodo.communicate(strInput)
		return out

	def cldDetect(self,string):
		return cld.detect(string,isPlainText=True,includeExtendedLanguages=False)

	def isEnglish(self,string):
		try:
			topLanguageName, topLanguageCode, isReliable, textBytesFound, details = self.cldDetect(string)
		except UnicodeEncodeError, e:
			#print "Cannot detect language of \"%s\"" % (string)
			print "errored"
			topLanguageCode = "nolang"
		return topLanguageCode == self.lang

	def loadState(self):
		state = None
		fd = open(self.twitterLog,"r")
		try:
			state = pickle.load(fd)
		except pickle.UnpicklingError, e:
			print "Error in unpickling: %s" % e
		return state

	def saveState(self):
		try:
			pickle.dump(self.state,open(self.twitterLog,"w"),-1)
		except pickle.PicklingError, e:
			print "Error in pickling: %s" % e

	def updateState(self):
		if self.state:
			stateTweets = { (x.GetText(), x.GetUser().GetId()) for x in self.state }
			# get all the followers for doaddoad
			allFollowers = self.api.GetFollowers()
			for each in allFollowers:
				print "Fetching timeline for user %s (@%s)" % (each.GetName(),each.GetScreenName())
				# get the timeline for the user
				timeline = self.api.GetUserTimeline(id=each.GetId(),count=20)
				# add all not-yet-seen tweets to the state
				for status in timeline:
					tweet = (status.GetText(), status.GetUser().GetId())
					if self.isEnglish(status.GetText()) and tweet not in stateTweets:
						self.state.append(status)
			if len(self.state) > self.stateLimit:
				self.state = self.state[:-(self.stateLimit)]
		else:
			print "FATAL: we got to update stage with an empty state!"
			sys.exit(124)
	
	def addAllFollowers(self):
		"""Automatically follow-back. Web 2.0 just got real."""

		followersNames = [x.GetScreenName() for x in self.api.GetFollowers()]
		followingNames = [x.GetScreenName() for x in self.api.GetFriends()]

		for user in set(followersNames).difference(set(followingNames)):
			newuser = self.api.CreateFriendship(user)
			print "following back: %s" % newuser

	def handleRt(self,string):
		"""Sometimes an RT might be generated in the middle of a sentence,
		   move it at the beginning and put @ in front of the next word."""

		pattern = re.compile(r"(^.*)([Rr][Tt]) +(\S+)\s(.*)$")
		matcher = pattern.match(string)
		if matcher:
			string = "RT @%s %s%s" % (matcher.group(3),matcher.group(1),matcher.group(4))
		return string

	def generateTweets(self):
		data = " ".join([ x.GetText() for x in self.state])
		out = self.launch(re.sub(r'\s', ' ', data.encode("ascii","ignore")))
		# remove tabulation
		out.replace("\t"," ")
		# strip leading whitespaces
		out.strip(" \t")
		if len(out) > 140:
			out = out[:140]
			out = out[:out.rindex(" ")]
		out = self.handleRt(out)
		return out.replace("\n","")
		

if __name__ == "__main__":
	d = DadaDodo()
	lastUpdateTime = os.stat(d.twitterLog).st_mtime
	saveState = False
	# check last time the cache was updated, if less than timeout, refresh it
	if lastUpdateTime <= (time.time() - d.refreshCacheTime):
		d.updateState()
		saveState =  True
		d.addAllFollowers()
	if d.debug:
		print d.generateTweets()
	else:
		d.api.PostUpdate(d.generateTweets())
	if saveState:
		d.saveState()
