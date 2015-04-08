#!/bin/env python
# encoding: utf-8

from flask import jsonify
from pymongo import MongoClient
import os
from flask import Flask, request
import re, time, json, pymongo
from collections import namedtuple


DB = 'tstream'
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'dbimports'
ALLOWED_EXTENSIONS = set(['csv'])
ENV = 'DEVELOPMENT'
D = True  # Turn on Debugging

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def get_profile_info():
    """
    Gets the profile information of the last executed query
    :param db: db connection
    :return: time in milli seconds
    """
    cursor = db.system.profile.find({"op": 'query'}, {"millis": 1}).sort("ts", pymongo.DESCENDING).limit(1)
    return cursor.next()['millis']


def fetch_records(coords, only_count=False):
    collection = db.tweets_tail
    query = {"loc": {"$geoWithin": {"$box": coords}}}
    log(query)
    cursor = collection.find(query, {"loc": 1, "_id": 0})
    start = time.clock()
    if (only_count):
        tweets = cursor.count()
    else:
        tweets = []
        for tweet in cursor:
            tweets.append(json.dumps(tweet))
    end = time.clock() - start
    log('Completed fetching tweets', True)
    return {"tweets": tweets, "time": end}


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


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


def log(message, only_debug=False):
    if only_debug:
        if D:
            print "\nD: {0} \n".format(message)
    else:
        print "\nD: {0} \n".format(message)


def fetch_environment_variable(key, default=None):
    value = default
    try:
        value = os.environ[key]
    finally:
        return value


def create_viz_index(win):
    """
    Creates a visualization index for the given window. The index is an aggreagation of tweets for each zoom level
    :param win: Southwest and Northeast co-ordinates of the query window.
    It is a dict type in this format {"sw": (long,lat), "ne": (long,lat)}
    :return: true if the index is successfully created, else false
    """
    point = namedtuple('point', 'long lat')
    box = namedtuple('box', 'sw ne nw se')
    ne = point(float(win["ne"][0]), float(win["ne"][1]))
    sw = point(float(win["sw"][0]), float(win['sw'][1]))
    nw = point(float(win['sw'][0]), float(win['ne'][1]))  # long from SW and lat from NE
    se = point(float(win['ne'][0]), float(win['sw'][1]))  # long from NE and lat from SW
    current_zoom = 3  # valid range [0 to 19]. 0 is the entire world
    longpieces = 8  # number of partitions at this zoom level along a latitude
    latpieces = 6  # number of partitions at this zoom level along a longitude
    longstep = abs(ne.long - nw.long) / longpieces
    latstep = abs(ne.lat - se.lat) / latpieces

    res = []

    for i in range(1, latpieces + 1):
        for j in range(1, longpieces + 1):
            current_win = box(point(nw.long, nw.lat - latstep), point(nw.long + longstep, nw.lat), nw,
                              point(nw.long + longstep, nw.lat - latstep))
            dbrecords = fetch_records(
                [[current_win.sw.long, current_win.sw.lat], [current_win.ne.long, current_win.ne.lat]], True)
            res.append(
                {'point': {'long': nw.long + longstep / 2, 'lat': nw.lat - latstep / 2},
                 'tweets': dbrecords['tweets'],
                 'time': dbrecords['time']})
            nw = point(nw.long + longstep, nw.lat)
        nw = point(nw.long - longpieces * longstep, nw.lat - latstep)
        log("i = {0}, j = {1}".format(i, j))
    return res


@app.route('/rect', methods=['GET', 'POST'])
def rect():
    log('Received req: {0}'.format(request.form))
    f = request.form
    # res = fetch_records([[float(f.get("ALong")), float(f.get("ALat"))], [float(f.get("BLong")), float(f.get("BLat"))]])
    res = create_viz_index({"sw": (-124, 27), "ne": (-59, 48)})
    return jsonify({"tweets": res['tweets'],
                    "apptime": res['time'],
                    "dbtime": get_profile_info()})


@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    log('Received req: {0}'.format(file))
    if file and allowed_file(file.filename):
        filepath = os.path.join(os.path.dirname(os.path.realpath(__file__)), UPLOAD_FOLDER, file.filename)
        file.save(filepath)  # to file system
        result = save_data_to_db(filepath)
        os.remove(filepath)
        return jsonify(
            {"files": [
                {"name": file.filename, "records": result["records_found"], "status": result["mongo_import"]}]})


ENV = fetch_environment_variable('ENV', ENV)
if str(fetch_environment_variable('DEBUG', D)) == 'False':
    D = False

if ENV == 'PRODUCTION':
    client = MongoClient("mongodb://admin:password@ds045679.mongolab.com:45679/tstream")
else:
    client = MongoClient()

db = client.tstream  # tstream is the name of the collection
db.set_profiling_level(pymongo.ALL)

if __name__ == '__main__':
    log('Running in {0} ENVIRONMENT'.format(ENV))
    # app.run(debug=True, host='0.0.0.0')
    create_viz_index({"sw": (-124, 27), "ne": (-59, 48)})
