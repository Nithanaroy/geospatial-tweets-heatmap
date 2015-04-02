Persisted GeoTagged Tweets Heatmap
==================================

Inspired from realtime tweet heatmap from https://github.com/comsysto/twitter-realtime-heatmap

* Download tweets from http://www.ark.cs.cmu.edu/GeoText 
* Tranform it into MongoDB documents using csv_mongo_json.py provided in the source code
* Start mongodb server using `mongod --profile=2`
* Use `mongoimport --db tsream --collection tweets_tail --type json --file path_from_above_step` to import the above document into mongodb
* Run `python tweet_servive.py` in terminal or command prompt
* Hit [http://localhost:5000/static/map.html](http://localhost:5000/static/map.html) and start drawing rectangles on the map
* Observe the generated status report on the side of the map and the heatmap

Done!
