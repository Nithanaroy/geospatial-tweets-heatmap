Persisted GeoTagged Tweets Heatmap
==================================

Inspired from realtime tweet heatmap from https://github.com/comsysto/twitter-realtime-heatmap

1. Download tweets from http://www.ark.cs.cmu.edu/GeoText 
2. Tranform it into MongoDB documents using csv_mongo_json.py provided in the source code
3. Start mongodb server using `mongod --profile=2`
4. Use `mongoimport --db tstream --collection tweets_tail --type json --file path_from_above_step` to import the above document into mongodb
5. Run `python tweet_servive.py` in terminal or command prompt
6. Visit [http://localhost:5000/static/map.html](http://localhost:5000/static/map.html) and start drawing rectangles on the map
7. Observe the generated status report on the side of the map and the heatmap

Done!
