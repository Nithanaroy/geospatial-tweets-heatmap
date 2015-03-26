import tweepy
import json
from pymongo import Connection
from bson import json_util
from tweepy.utils import import_simplejson


json = import_simplejson()
mongocon = Connection()

db = mongocon.tstream
col = db.tweets_tail

consumer_key = '2faSWhbSHTxcknwVWyIWSwsqZ'
consumer_secret = 'xkBkj0R95Npb1cye5xO14ovQMKW6sRtEyvGLIbZLO6sHHXe7mb'

access_token_key = '57263362-r4nloUysewcitMVF2yTRCGVxSKHi9hz2eOR91z7ya'
access_token_secret = 'yNgl0RkzRvXKwRSKMVn3UBKjAkrRJ3VcbthFu5C3XLLqu'

auth1 = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth1.set_access_token(access_token_key, access_token_secret)


class StreamListener(tweepy.StreamListener):
    mongocon = Connection()
    db = mongocon.tstream
    col = db.tweets
    json = import_simplejson()


    def on_status(self, tweet):
        print 'Ran on_status'

    def on_error(self, status_code):
        return False

    def on_data(self, data):
        if data[0].isdigit():
            pass
        else:
            col.insert(json.loads(data))
            print(json.loads(data))


l = StreamListener()
streamer = tweepy.Stream(auth=auth1, listener=l)
setTerms = ['bigdata', 'devops', 'hadoop', 'twitter']
streamer.filter(track=setTerms)
