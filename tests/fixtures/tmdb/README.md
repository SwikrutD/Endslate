# Recorded TMDB responses

`responses.json` holds real search results and season listings, recorded once by
`scripts/record_tmdb.py` and replayed by `tests/test_tmdb_live_fixtures.py`.

Only response bodies are stored. The API key lives in the request URL and never
reaches this folder, and the recorder refuses to write if it finds the key in the
payload anyway.

It is committed, so the replay tests run everywhere. They skip themselves if the
file is ever missing. Re-record whenever a matcher change needs proving against
real data:

    python scripts/record_tmdb.py
