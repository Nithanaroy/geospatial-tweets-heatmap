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
from flask import request
from pymongo import Connection
from bson import json_util
from flask import jsonify

from pymongo import MongoClient

import time

red = redis.StrictRedis()


def signal_handler(signal, frame):
    print 'You pressed Ctrl+C!'
    sys.exit(0)


# def tail_mongo_thread():
# print "beginning to tail..."
# db = Connection().tstream
# coll = db.tweets_tail
# cursor = coll.find({"coordinates.type": "Point"}, {"coordinates": 1}, tailable=True, timeout=False)
# ci = 0
# while cursor.alive:
# try:
# doc = cursor.next()
# ci += 1
# red.publish('chat', u'%s' % json.dumps(doc, default=json_util.default))
# except StopIteration:
# pass

coords = [[-141.835688, 48.028172], [-74.687255, 68.355474]]


def tail_mongo_thread():
    client = MongoClient()
    db = client.tstream
    collection = db.tweets_tail
    # cursor = collection.find({"coordinates.type": "Point"}, {"coordinates": 1})
    usa = [[-127.103022, 33.332402], [-56.318116, 50.966758]]
    canada = [[-141.835688, 48.028172], [-74.687255, 68.355474]]
    africa = [[-21.299549, -32.582041], [33.719978, 31.017117]]
    northasia = [[36.005138, 44.183743], [137.218481, 74.667217]]
    southasia = [[40.569780, 14.789655], [145.159617, 55.287816]]
    australia = [[106.261201, -35.578352], [157.589323, -11.320211]]
    southamerica = [[-93.727095, -52.258807], [-30.094287, 12.397849]]
    ustoplleft = [[-127.450990, 41.705594], [-105.123861, 48.562837]]
    ustopright = [[-103.366048, 40.966260], [-61.705895, 49.141154]]
    usbottomleft = [[-125.162922, 32.234697], [-102.487142, 38.534037]]
    usbottomright = [[-100.905111, 30.129506], [-73.307457, 37.285905]]  # 78, 282
    cursor = collection.find({"loc": {"$geoWithin": {"$box": coords}}})
    for tweet in cursor:
        # print(tweet)
        red.publish('chat', u'%s' % json.dumps(tweet, default=json_util.default))
        # time.sleep(0.0001)


def fetch_records(coords):
    client = MongoClient()
    db = client.tstream
    collection = db.tweets_tail
    cursor = collection.find({"loc": {"$geoWithin": {"$box": coords}}}, {"loc": 1, "_id": 0})
    tweets = []
    for tweet in cursor:
        tweets.append(json.dumps(tweet, default=json_util.default))
    return tweets


def event_stream():
    pubsub = red.pubsub()
    pubsub.subscribe('chat')
    i = 0
    for message in pubsub.listen():
        i += 1
        # if 10000 % i == 0:
        print i
        # time.sleep(0.5)
        yield 'data: %s\n\n' % message['data']


app = Flask(__name__)


@app.route('/rect', methods=['GET', 'POST'])
def rect():
    print request.form
    # return Response({"val": "yipppeee"}, headers={'Content-Type': 'application/json'})
    f = request.form
    return jsonify({"tweets": fetch_records(
        [[float(f.get("ALong")), float(f.get("ALat"))], [float(f.get("BLong")), float(f.get("BLat"))]])})


@app.route('/tweets')
def tweets():
    url_for('static', filename='map.html')
    url_for('static', filename='jquery-1.7.2.min.js')
    url_for('static', filename='jquery.eventsource.js')
    url_for('static', filename='jquery-1.7.2.js')
    # return Response(event_stream(), headers={'Content-Type': 'text/event-stream'})
    return "Hello World!"


def runThread():
    st = Thread(target=tail_mongo_thread)
    st.start()


if __name__ == '__main__':
    # signal.signal(signal.SIGINT, signal_handler)
    # app.before_first_request(runThread)
    app.run(debug=True, host='0.0.0.0')  
