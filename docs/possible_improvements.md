This is a quick project/poc for fun. But here are my (non ai) analysis.
Let's call it a review for learning.

1. I would like a bit less mocking in the tests. Having a test db would help with that.
2. The db and schema shouldn't be in play text in database.py instead sqlalchemy or SQLModel could be used
3. Could Use a library for base62 (pybase62). Smaller but add a dependancy (trade-off)
4. Use ORM for queries instead of sql
5. home most used url is based on created at instead of count. join could be removed for denormalization
6. UI wise suggestion are not needed
7. JS is doing a bit too much. I like the ajax but less the injecting of html inline

### Trade-off
The main part of this app is the algo for getting an short hash for an url.
The requirement "as short as possible" make it so that we have to figure out the minimal
amount of character needed. We have 26(alphabet)*2(up/downcase)+10(digit) char =>62.
62^N > number of projected saved URL. In this fictive case for 100k it's N=3.
This bring us to an uncomfortable % of filled values at capacity ~(100k/238k capacity).
One solution is to set N to 4, but in this cases I wanted to deal with collision.

Possible solution include: 
1. Using hashing algo like sha256, MD5, etc.
2. Using Base62

Other requirements like non-guessable URL add a layer to the problem.

If we were going with 1. we would need to get the N first alphanumerical char from hashing the full URL or getting a random ID. On collision we would re-generate a new hash and add a random prefix/suffix that would be scrapped later on retrieval.

Using Base62 on the id would result in sequential URL. We can generate unique IDs but have to possibly handle collision and/or non-sequentials id in the db. In a distributed env, we could use snowflake to generate random distributed IDs. Base62 is not of fixed length.
