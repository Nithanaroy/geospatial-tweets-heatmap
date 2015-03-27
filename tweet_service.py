#!/bin/env python
# encoding: utf-8

"""
Webservice prototype for exposing cell data via
HTTP and JSON/JSONP
"""

DB = 'tstream'
CELLS_COLLECTION = 'tweets'

import json
import signal
import sys
from threading import Thread

import redis
from flask import Flask
from flask import url_for
from flask import Response
from pymongo import Connection
from bson import json_util

from pymongo import MongoClient

import time

red = redis.StrictRedis()


def signal_handler(signal, frame):
    print 'You pressed Ctrl+C!'
    sys.exit(0)


# def tail_mongo_thread():
# print "beginning to tail..."
#     db = Connection().tstream
#     coll = db.tweets_tail
#     cursor = coll.find({"coordinates.type": "Point"}, {"coordinates": 1}, tailable=True, timeout=False)
#     ci = 0
#     while cursor.alive:
#         try:
#             doc = cursor.next()
#             ci += 1
#             red.publish('chat', u'%s' % json.dumps(doc, default=json_util.default))
#         except StopIteration:
#             pass


def tail_mongo_thread():
    client = MongoClient()
    db = client.tstream
    collection = db.tweets_tail
    # cursor = collection.find({"coordinates.type": "Point"}, {"coordinates": 1})
    cursor = collection.find({})
    for tweet in cursor:
        # print(tweet)
        red.publish('chat', u'%s' % json.dumps(tweet, default=json_util.default))
        # time.sleep(0.0001)


def event_stream():
    pubsub = red.pubsub()
    pubsub.subscribe('chat')
    i = 0
    for message in pubsub.listen():
        i += 1
        if 10000 % i == 0:
            print i
            time.sleep(0.5)
        yield 'data: %s\n\n' % message['data']


app = Flask(__name__)


@app.route('/tweets')
def tweets():
    url_for('static', filename='map.html')
    url_for('static', filename='jquery-1.7.2.min.js')
    url_for('static', filename='jquery.eventsource.js')
    url_for('static', filename='jquery-1.7.2.js')
    return Response(event_stream(), headers={'Content-Type': 'text/event-stream'})


def runThread():
    st = Thread(target=tail_mongo_thread)
    st.start()


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    app.before_first_request(runThread)
    app.run(debug=True, host='0.0.0.0')  
