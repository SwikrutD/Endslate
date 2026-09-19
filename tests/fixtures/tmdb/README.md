# Recorded TMDB responses

`responses.json` holds real search results and season listings, recorded once by
`scripts/record_tmdb.py` and replayed by `tests/test_tmdb_live_fixtures.py`.

Only response bodies are stored. The API key lives in the request URL and never
reaches this folder, and the recorder refuses to write if it finds the key in the
payload anyway.

The file is absent until someone with network access to TMDB records it, and the
tests that use it skip themselves when it is missing. Re-record whenever a
matcher change needs proving against real data:

    python scripts/record_tmdb.py
