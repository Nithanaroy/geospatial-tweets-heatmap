#!/bin/env python
# encoding: utf-8

from flask import jsonify
from pymongo import MongoClient, GEO2D
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
    # log(query)

    start = time.clock()
    if only_count:
        tweets = collection.count(query)
        end = 0  # Nothing to do on server
    else:
        cursor = collection.find(query, {"loc": 1, "_id": 0})
        tweets = []
        for tweet in cursor:
            tweets.append(json.dumps(tweet))
        end = time.clock() - start
    # log('Completed fetching tweets', True)
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
        # MongoLab Vendor
        status = os.system(
            'mongoimport --host ds045679.mongolab.com --port 45679 --db tstream  -u admin -p password --collection tweets_tail --type json --file "' + converted + '"')

        # Mongo Soup Vendor
        # status = os.system(
        # 'mongoimport --host mongosoup-cont002.mongosoup.de --port 32486 --db tstream  -u admin -p password --collection tweets_tail --type json --file "' + converted + '"')
    else:
        status = os.system('mongoimport --db tstream --collection tweets_tail --type json --file  "' + converted + '"')

    log("MongoDB Import Status (0 => success): {0}".format(status))

    os.remove(converted)

    db.tweets_tail.create_index([("loc", GEO2D)])

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


def aggregate_tweets(current_zoom, latpieces, longpieces, win):
    """
    The core method used for aggregating the tweets in a given window
    The window is split along the longitude into latpieces and along the latitude into longpieces
    Then the tweets in each piece (box) are aggregated and the center of the point is chosen as the
    representative of that box. The final result of such aggregation would be [{center: count}, {center: count} ...]
    :param current_zoom: Zoom level of the map
    :param latpieces: Number of cuts along a longitude
    :param longpieces: Number of cuts along a latittude
    :param win: Southwest and Northeast co-ordinates of the window to split and aggregate on
    :return: [{'loc': [longitude, latitude], 'count': dbrecords['tweets'], 'dbtime': dbrecords['time']}, ... ]
    """
    log("Started aggregating for Zoom {0}. Rows: {1}. Columns {2}".format(current_zoom, longpieces, latpieces))
    point = namedtuple('point', 'long lat')
    box = namedtuple('box', 'sw ne nw se')
    ne = point(float(win["ne"][0]), float(win["ne"][1]))
    sw = point(float(win["sw"][0]), float(win['sw'][1]))
    nw = point(float(win['sw'][0]), float(win['ne'][1]))  # long from SW and lat from NE
    se = point(float(win['ne'][0]), float(win['sw'][1]))  # long from NE and lat from SW
    longstep = abs(ne.long - nw.long) / longpieces
    latstep = abs(ne.lat - se.lat) / latpieces
    res = []

    for i in range(1, latpieces + 1):
        start = time.clock()
        for j in range(1, longpieces + 1):
            current_win = box(point(nw.long, nw.lat - latstep), point(nw.long + longstep, nw.lat), nw,
                              point(nw.long + longstep, nw.lat - latstep))
            dbrecords = fetch_records(
                [[current_win.sw.long, current_win.sw.lat], [current_win.ne.long, current_win.ne.lat]], True)
            res.append(
                {'loc': [nw.long + longstep / 2, nw.lat - latstep / 2],
                 'count': dbrecords['tweets'],
                 'dbtime': dbrecords['time']})
            nw = point(nw.long + longstep, nw.lat)
        nw = point(nw.long - longpieces * longstep, nw.lat - latstep)
        print("row {0} of {1}. Took {2}s".format(i, latpieces, time.clock() - start))
    log("Completed for zoom level " + str(current_zoom))
    return res


def create_viz_index(win, zoom_levels=None):
    """
    Creates a visualization index for the given window. The index is an aggreagation of tweets for each zoom level
    :param win: Southwest and Northeast co-ordinates of the query window.
    It is a dict type in this format {"sw": (long,lat), "ne": (long,lat)}
    :param zoom_levels: Zoom levels to generate the index for. If None, all levels are considered => [3, 6, 9]
    :return: true if the index is successfully created, else false
    """

    # Key => Zoom Level. Value => {longpieces: #, latpieces: #}
    # Google Maps Zoom Level: valid range [0 to 19]. 0 is the entire world
    zoom_split = {3: {"longpieces": 2, "latpieces": 2}, 4: {"longpieces": 4, "latpieces": 4},
                  5: {"longpieces": 8, "latpieces": 8}, 6: {"longpieces": 16, "latpieces": 16},
                  7: {"longpieces": 32, "latpieces": 32}, 8: {"longpieces": 64, "latpieces": 64},
                  9: {"longpieces": 128, "latpieces": 128}, 10: {"longpieces": 256, "latpieces": 256},
                  11: {"longpieces": 512, "latpieces": 512}}

    if zoom_levels is None:
        zoom_levels = zoom_split.keys()

    for current_zoom in zoom_levels:
        start = time.clock()
        longpieces = zoom_split[current_zoom]['longpieces']  # number of partitions at this zoom level along a latitude
        latpieces = zoom_split[current_zoom]['latpieces']  # number of partitions at this zoom level along a longitude

        # res = aggregate_tweets_dummy(current_zoom, latpieces, longpieces, win)
        res = aggregate_tweets(current_zoom, latpieces, longpieces, win)

        # Save to MongoDB into vizindex collection
        for tweet in res:
            # Merge this info along with the tweet data using update()
            tweet.update(
                {"win": [[float(win["sw"][0]), float(win['sw'][1])], [float(win["ne"][0]), float(win["ne"][1])]],
                 "zoom": current_zoom, "longpieces": longpieces, "latpieces": latpieces})
            db.vizindex.insert(tweet)
        end = time.clock() - start
        print('Zoom: {0}. Time taken: {1}s'.format(current_zoom, end))
        print('===============================================')
    db.vizindex.create_index([("loc", GEO2D)])
    return True


@app.route('/createIndex', methods=['GET', 'POST'])
def create_index():
    """
    Creates an index for the given window
    :return:
    """
    log("Create Index: Received req: {0}".format(request.form))
    # res = create_viz_index({"sw": (-124, 27), "ne": (-59, 48)}, [int(i) for i in request.form['zoom']])
    res = create_viz_index({"sw": (-124, 27), "ne": (-59, 48)}, [int(request.form['zoom'])])
    return "Success!"


@app.route('/rectWithIndex', methods=['GET', 'POST'])
def rect_with_index():
    """
    Retrieves data from an index
    Request's ContentType should be application/json: {u'win': [[-124, 27], [-59, 48]], u'zoom_level': 3}
    :return:
    data = {"tweets":{
       "counts":[{"count":17011,"loc":[-107.75,42.75]},{"count":214831,"loc":[-75.25,42.75]},{"count":53548,"loc":[-107.75,32.25]},{"count":79089,"loc":[-75 25,32.25]}],
       "latpieces":2,
       "longpieces":2,
       "win":[[-124,27],[-59,48]],"zoom":3}
    }
    """
    log('Query with Index: Received req: {0}'.format(request.json))
    # cursor = db.vizindex.find({"win": request.json['win'], "zoom": request.json['zoom_level']},
    # {"_id": 0, "counts.dbtime": 0})

    query = {"win": request.json['win'], "zoom": 8, "loc": {"$geoWithin": {"$box": request.json['bounds']}},
             "count": {"$gt": 0}}
    log('Query to DB: {0}'.format(query))
    cursor = db.vizindex.find(query, {"_id": 0, "dbtime": 0, "latpieces": 0, "longpieces": 0, "win": 0, "zoom": 0})
    # if cursor.count() > 0:
    # tweets = cursor.next()  # There will be only one entry for each {zoom, window} combination
    # return jsonify({"tweets": tweets})
    # else:
    # return jsonify({"tweets": None})

    tweets = []
    for tweet in cursor:
        tweets.append(tweet)
    return jsonify({"tweets": tweets})


@app.route('/rect', methods=['GET', 'POST'])
def rect():
    log('Received req: {0}'.format(request.form))
    f = request.form
    res = fetch_records([[float(f.get("ALong")), float(f.get("ALat"))], [float(f.get("BLong")), float(f.get("BLat"))]])
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
    # Mongo Lab Vendor
    client = MongoClient("mongodb://admin:password@ds045679.mongolab.com:45679/tstream")
    # Mongo Soup Vendor
    # client = MongoClient("mongodb://admin:password@mongosoup-cont002.mongosoup.de:32486/tstream")
else:
    client = MongoClient()

db = client.tstream  # tstream is the name of the collection
db.set_profiling_level(pymongo.ALL)

if __name__ == '__main__':
    log('Running in {0} ENVIRONMENT'.format(ENV))
    app.run(debug=True, host='0.0.0.0')
    # create_viz_index({"sw": (-124, 27), "ne": (-59, 48)})
