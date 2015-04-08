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
                 'count': dbrecords['tweets'],
                 'dbtime': dbrecords['time']})
            nw = point(nw.long + longstep, nw.lat)
        nw = point(nw.long - longpieces * longstep, nw.lat - latstep)
    log("Completed for zoom level " + str(current_zoom))
    return res


def create_viz_index_dummy(win):
    return [{'count': 3091, 'dbtime': 0.8059939126730346, 'point': {'lat': 46.25, 'long': -119.9375}},
            {'count': 29, 'dbtime': 0.7568107744660757, 'point': {'lat': 46.25, 'long': -111.8125}},
            {'count': 30, 'dbtime': 0.7987609774625191, 'point': {'lat': 46.25, 'long': -103.6875}},
            {'count': 1569, 'dbtime': 0.7580918847616651, 'point': {'lat': 46.25, 'long': -95.5625}},
            {'count': 166, 'dbtime': 0.8029379308220972, 'point': {'lat': 46.25, 'long': -87.4375}},
            {'count': 392, 'dbtime': 0.7594982318008938, 'point': {'lat': 46.25, 'long': -79.3125}},
            {'count': 967, 'dbtime': 0.7677854140254885, 'point': {'lat': 46.25, 'long': -71.1875}},
            {'count': 355, 'dbtime': 0.762021444226022, 'point': {'lat': 46.25, 'long': -63.0625}},
            {'count': 722, 'dbtime': 0.769122983508784, 'point': {'lat': 42.75, 'long': -119.9375}},
            {'count': 25, 'dbtime': 0.7728292725490293, 'point': {'lat': 42.75, 'long': -111.8125}},
            {'count': 80, 'dbtime': 0.7760192166544337, 'point': {'lat': 42.75, 'long': -103.6875}},
            {'count': 679, 'dbtime': 0.8107144140306222, 'point': {'lat': 42.75, 'long': -95.5625}},
            {'count': 15470, 'dbtime': 0.7686851681713893, 'point': {'lat': 42.75, 'long': -87.4375}},
            {'count': 21022, 'dbtime': 0.7657390251038088, 'point': {'lat': 42.75, 'long': -79.3125}},
            {'count': 15812, 'dbtime': 0.768177035482033, 'point': {'lat': 42.75, 'long': -71.1875}},
            {'count': 0, 'dbtime': 0.774762229829955, 'point': {'lat': 42.75, 'long': -63.0625}},
            {'count': 8121, 'dbtime': 0.7571510693883425, 'point': {'lat': 39.25, 'long': -119.9375}},
            {'count': 152, 'dbtime': 0.7601490522555441, 'point': {'lat': 39.25, 'long': -111.8125}},
            {'count': 960, 'dbtime': 0.7812216741688953, 'point': {'lat': 39.25, 'long': -103.6875}},
            {'count': 1553, 'dbtime': 0.8682488926300227, 'point': {'lat': 39.25, 'long': -95.5625}},
            {'count': 8540, 'dbtime': 0.7605925135117104, 'point': {'lat': 39.25, 'long': -87.4375}},
            {'count': 35777, 'dbtime': 0.7683638640668065, 'point': {'lat': 39.25, 'long': -79.3125}},
            {'count': 116330, 'dbtime': 0.7592872797450099, 'point': {'lat': 39.25, 'long': -71.1875}},
            {'count': 0, 'dbtime': 0.7572265193937326, 'point': {'lat': 39.25, 'long': -63.0625}},
            {'count': 11894, 'dbtime': 0.7626732912113603, 'point': {'lat': 35.75, 'long': -119.9375}},
            {'count': 2000, 'dbtime': 0.7664273139284816, 'point': {'lat': 35.75, 'long': -111.8125}},
            {'count': 270, 'dbtime': 0.7600715491887833, 'point': {'lat': 35.75, 'long': -103.6875}},
            {'count': 2331, 'dbtime': 0.7723170337369325, 'point': {'lat': 35.75, 'long': -95.5625}},
            {'count': 8185, 'dbtime': 0.807729776062331, 'point': {'lat': 35.75, 'long': -87.4375}},
            {'count': 26813, 'dbtime': 0.7628811636751855, 'point': {'lat': 35.75, 'long': -79.3125}},
            {'count': 0, 'dbtime': 0.7632342902310221, 'point': {'lat': 35.75, 'long': -71.1875}},
            {'count': 0, 'dbtime': 0.777394254507751, 'point': {'lat': 35.75, 'long': -63.0625}},
            {'count': 14822, 'dbtime': 0.760802952302253, 'point': {'lat': 32.25, 'long': -119.9375}},
            {'count': 3753, 'dbtime': 0.7665633292443204, 'point': {'lat': 32.25, 'long': -111.8125}},
            {'count': 359, 'dbtime': 0.7730207205218882, 'point': {'lat': 32.25, 'long': -103.6875}},
            {'count': 5277, 'dbtime': 0.7674671895129634, 'point': {'lat': 32.25, 'long': -95.5625}},
            {'count': 26200, 'dbtime': 0.7595054175156939, 'point': {'lat': 32.25, 'long': -87.4375}},
            {'count': 5583, 'dbtime': 0.768115956906243, 'point': {'lat': 32.25, 'long': -79.3125}},
            {'count': 17, 'dbtime': 0.7853796367107932, 'point': {'lat': 32.25, 'long': -71.1875}},
            {'count': 164, 'dbtime': 0.7816836129773996, 'point': {'lat': 32.25, 'long': -63.0625}},
            {'count': 0, 'dbtime': 0.7587334664401482, 'point': {'lat': 28.75, 'long': -119.9375}},
            {'count': 263, 'dbtime': 0.776628975881664, 'point': {'lat': 28.75, 'long': -111.8125}},
            {'count': 130, 'dbtime': 0.7806647812719802, 'point': {'lat': 28.75, 'long': -103.6875}},
            {'count': 12449, 'dbtime': 0.7720655337189726, 'point': {'lat': 28.75, 'long': -95.5625}},
            {'count': 5049, 'dbtime': 0.786970759273423, 'point': {'lat': 28.75, 'long': -87.4375}},
            {'count': 7078, 'dbtime': 0.7655804261128907, 'point': {'lat': 28.75, 'long': -79.3125}},
            {'count': 0, 'dbtime': 0.7664180751523162, 'point': {'lat': 28.75, 'long': -71.1875}},
            {'count': 0, 'dbtime': 0.7594268879182451, 'point': {'lat': 28.75, 'long': -63.0625}}]


@app.route('/rectWithIndex', methods=['GET', 'POST'])
def rect_with_index():
    log('Received req: {0}'.format(request.form))
    # f = request.form
    # res = fetch_records([[float(f.get("ALong")), float(f.get("ALat"))], [float(f.get("BLong")), float(f.get("BLat"))]])
    res = create_viz_index_dummy({"sw": (-124, 27), "ne": (-59, 48)})
    return jsonify({"tweets": res})


@app.route('/rect', methods=['GET', 'POST'])
def rect():
    log('Received req: {0}'.format(request.form))
    f = request.form
    res = fetch_records([[float(f.get("ALong")), float(f.get("ALat"))], [float(f.get("BLong")), float(f.get("BLat"))]])
    # res = create_viz_index({"sw": (-124, 27), "ne": (-59, 48)})
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
    app.run(debug=True, host='0.0.0.0')
    # create_viz_index({"sw": (-124, 27), "ne": (-59, 48)})
