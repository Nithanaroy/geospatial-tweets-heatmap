#!/bin/env python
# encoding: utf-8

from flask import jsonify
from pymongo import MongoClient
import os
from flask import Flask, request
import re, time, json, pymongo

DB = 'tstream'
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
        tweets.append(json.dumps(tweet))
    end = time.clock() - start
    log('Completed fetching tweets', True)
    return {"tweets": tweets, "time": end}


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


def log(message, only_debug=False):
    if only_debug:
        if D:
            print "\nD: {0} \n".format(message)
    else:
        print "\nD: {0} \n".format(message)


log('Running in {0} ENVIRONMENT'.format(ENV))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
