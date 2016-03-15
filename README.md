Persisted GeoTagged Tweets Heatmap
==================================

Boilerplate code taken from https://github.com/comsysto/twitter-realtime-heatmap

## About
The main intent of this project is to observe the performance gained by using an index for visualizing huge set of tweets on a world map. Here, these tweets are visualized via heatmap. The module `tweet_service.py` has a function, `create_viz_index()`, which creates an index from raw data once imported using the steps mentioned in the installation section. After creating the index, launch the app to see heatmap drawn using the index for black bounding box shown. The side panel shows some statistics about this call. In order to compare the time it takes to perform the same action without an index, use the rectangle tool at the top and draw a rectangle of the same size. Like this, using the same app, we can compare the statistics with and without the index.

## Installation

1. Download tweets from http://www.ark.cs.cmu.edu/GeoText 
2. Tranform it into MongoDB documents using csv_mongo_json.py provided in the source code
3. Start mongodb server using `mongod --profile=2`
4. Use `mongoimport --db tstream --collection tweets_tail --type json --file path_from_above_step` to import the above document into mongodb
5. Run `python tweet_servive.py` in terminal or command prompt
6. Visit [http://localhost:5000/static/map.html](http://localhost:5000/static/map.html) and start drawing rectangles on the map
7. Observe the generated status report on the side of the map and the heatmap

### Index creation

1. Open terminal or command prompt and start python REPL, using `python` command
2. Import `tweet_service.py` as a module, `import tweet_service as t`
3. Run, 
```
for i in range(3, 12):
    t.create_viz_index({"sw": (-124, 27), "ne": (-59, 48)}, [i])
````
This will create another collection in mongo db.

Done!
