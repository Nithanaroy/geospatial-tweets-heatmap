#!/bin/env python
# encoding: utf-8

"""
Webservice prototype for exposing cell data via
HTTP and JSON/JSONP
"""

DB = 'tstream'

import json
# import redis
# from bson import json_util

from flask import jsonify
import sys
from threading import Thread
from pymongo import MongoClient
import os
from flask import Flask, request, redirect, url_for
import re, time, json, pymongo

UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'dbimports'
ALLOWED_EXTENSIONS = set(['csv'])
ENV = 'DEVELOPMENT'
D = True  # Turn on Debugging

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

try:
    if os.environ['ENV'] == 'PRODUCTION':
        ENV = 'PRODUCTION'
    if os.environ['DEBUG'] == 'False':
        D = False
except:
    pass

if ENV == 'PRODUCTION':
    client = MongoClient("mongodb://admin:password@ds045679.mongolab.com:45679/tstream")
else:
    client = MongoClient()
db = client.tstream
db.set_profiling_level(pymongo.ALL)



# red = redis.StrictRedis()


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
    cursor = collection.find({"loc": {"$geoWithin": {"$box": usa}}})
    # for tweet in cursor:
    # print(tweet)
    # red.publish('chat', u'%s' % json.dumps(tweet, default=json_util.default))
    # time.sleep(0.0001)


def get_profile_info():
    """
    Gets the profile information of the last executed query
    :param db: db connection
    :return: time in milli seconds
    """
    cursor = db.system.profile.find({"op": 'query'}, {"millis": 1}).sort("ts", pymongo.DESCENDING).limit(1)
    return cursor.next()['millis']


def fetch_records(coords):
    collection = db.tweets_tail
    query = {"loc": {"$geoWithin": {"$box": coords}}}
    log(query)
    cursor = collection.find(query, {"loc": 1, "_id": 0})
    start = time.clock()
    tweets = []
    for tweet in cursor:
        # tweets.append(json.dumps(tweet, default=json_util.default))
        tweets.append(json.dumps(tweet))
    end = time.clock() - start
    log('Completed fetching tweets', True)
    return {"tweets": tweets, "time": end}


# def event_stream():
# # pubsub = red.pubsub()
# pubsub.subscribe('chat')
# i = 0
# for message in pubsub.listen():
# i += 1
# # if 10000 % i == 0:
# print i
# # time.sleep(0.5)
# yield 'data: %s\n\n' % message['data']


app = Flask(__name__)


@app.route('/rect', methods=['GET', 'POST'])
def rect():
    log('Received req: {0}'.format(request.form))
    f = request.form
    res = fetch_records([[float(f.get("ALong")), float(f.get("ALat"))], [float(f.get("BLong")), float(f.get("BLat"))]])
    return jsonify({"tweets": res['tweets'],
                    "apptime": res['time'],
                    "dbtime": get_profile_info()})


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        file = request.files['file']
        log('Received req: {0}'.format(file))
        if file and allowed_file(file.filename):
            # filename = secure_filename(file.filename)
            filepath = os.path.join(os.path.dirname(os.path.realpath(__file__)), UPLOAD_FOLDER, file.filename)
            file.save(filepath)  # to file system
            result = save_data_to_db(filepath)
            os.remove(filepath)
            return jsonify(
                {"files": [
                    {"name": file.filename, "records": result["records_found"], "status": result["mongo_import"]}]})


def save_data_to_db(filepath):
    converted = os.path.join(os.path.dirname(os.path.realpath(__file__)), PROCESSED_FOLDER,
                             str(int(time.time())) + ".json")
    log('Converting {0} to {1}'.format(filepath, converted))
    count = 0
    with open(filepath, "r") as fr:
        with open(converted, "w") as fw:
            keys = [x.strip() for x in fr.next().split(",")]  # ignore the header line of csv
            for line in fr:
                temp = re.split(r',', line.strip())  # long, lat, other data
                obj = {"loc": [float(temp[0]), float(temp[1])]}
                # save the other keys
                for i, k in enumerate(keys[2:]):
                    if len(k) == 0: continue  # ignore column when corresponding key is empty
                    obj[k] = temp[i + 2]
                fw.write('%s\n' % (json.dumps(obj), ))  # longitude, latitude
                count += 1

    log('Completed conversion', True)

    status = 0
    if ENV == 'PRODUCTION':
        status = os.system(
            'mongoimport --host ds045679.mongolab.com --port 45679 --db tstream  -u admin -p password --collection tweets_tail --type json --file "' + converted + '"')
    else:
        status = os.system('mongoimport --db tstream --collection tweets_tail --type json --file  "' + converted + '"')

    log("MongoDB Import Status (0 => success): {0}".format(status))

    os.remove(converted)

    return {"records_found": count, "mongo_import": status}

    # @app.route('/tweets')
    # def tweets():
    # url_for('static', filename='map.html')
    # url_for('static', filename='jquery-1.7.2.min.js')
    # url_for('static', filename='jquery.eventsource.js')
    # url_for('static', filename='jquery-1.11.2.min.js')
    # url_for('static', filename='twitter.ico')
    # # return Response(event_stream(), headers={'Content-Type': 'text/event-stream'})
    # return "Hello World!"


def log(message, only_debug=False):
    if only_debug:
        if D:
            print "\nD: {0} \n".format(message)
    else:
        print "\nD: {0} \n".format(message)


log('Running in {0} ENVIRONMENT'.format(ENV))


def runThread():
    st = Thread(target=tail_mongo_thread)
    st.start()


if __name__ == '__main__':
    # signal.signal(signal.SIGINT, signal_handler)
    # app.before_first_request(runThread)
    app.run(debug=True, host='0.0.0.0')  
