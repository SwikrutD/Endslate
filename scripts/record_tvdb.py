"""Record real TheTVDB responses as test fixtures, as record_tmdb.py does for TMDB.

    python scripts/record_tvdb.py

The key is read from %LOCALAPPDATA%\\Endslate\\config.json, or from TVDB_API_KEY.
Neither it nor the session token is written to the fixtures: only trimmed
response bodies are saved, keyed by the request that produced them, and the
recorder refuses to write if either secret turns up in the payload anyway.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from endslate.config import load_config  # noqa: E402
from endslate.tvdb import API, MAX_PAGES  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "tvdb"
LANGUAGE = "eng"

# The names fansub groups actually use, the year where one is usually given,
# and one search that is ambiguous on purpose.
SEARCHES = [
    ("Sousou no Frieren", None),
    ("Sousou no Frieren", 2023),
    ("One Piece", None),
    ("Shingeki no Kyojin", None),
    ("Spy x Family", None),
    ("Mob Psycho 100", None),
    ("Dandadan", None),
    ("Naruto Shippuden", None),
]

EPISODES = [424536, 81797, 267440, 405920, 432832]
SERIES = [424536]


def request_key(path: str, params: dict) -> str:
    return path + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))


def trim_search_row(row: dict) -> dict:
    keep = ("tvdb_id", "name", "year", "primary_language", "image_url", "aliases")
    out = {k: row.get(k) for k in keep}
    translations = row.get("translations") or {}
    out["translations"] = {k: v for k, v in translations.items() if k in (LANGUAGE, "jpn")}
    overviews = row.get("overviews") or {}
    out["overviews"] = {k: (v or "")[:200] for k, v in overviews.items() if k == LANGUAGE}
    return out


def trim_episode(row: dict) -> dict:
    return {k: row.get(k) for k in ("seasonNumber", "number", "absoluteNumber", "name")}


def main() -> int:
    key = os.environ.get("TVDB_API_KEY") or load_config().tvdb_api_key
    if not key:
        print("No TheTVDB key. Put one in Settings, or set TVDB_API_KEY.", file=sys.stderr)
        return 2
    import requests

    session = requests.Session()
    login = session.post(f"{API}/login", json={"apikey": key}, timeout=20)
    login.raise_for_status()
    token = login.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}

    def fetch(path: str, params: dict):
        response = session.get(f"{API}{path}", params=params, headers=headers, timeout=30)
        time.sleep(0.25)
        if response.status_code == 404:
            return {}
        response.raise_for_status()
        return response.json()

    recorded: dict[str, dict] = {}

    for name, year in SEARCHES:
        params = {"query": name, "type": "series"}
        if year:
            params["year"] = year
        data = fetch("/search", params)
        rows = [trim_search_row(r) for r in (data.get("data") or [])[:10]]
        recorded[request_key("/search", params)] = {"data": rows}
        print(f"search  {name:28} {year or '':6} {len(rows)} results")

    for series_id in EPISODES:
        path = f"/series/{series_id}/episodes/default/{LANGUAGE}"
        for page in range(MAX_PAGES):
            data = fetch(path, {"page": page})
            episodes = [trim_episode(e) for e in ((data.get("data") or {}).get("episodes") or [])]
            links = data.get("links") or {}
            recorded[request_key(path, {"page": page})] = {
                "data": {"episodes": episodes},
                "links": {"next": bool(links.get("next"))},
            }
            print(f"episodes {series_id:<10} page {page}  {len(episodes)} episodes")
            if not links.get("next") or not episodes:
                break

    for series_id in SERIES:
        data = (fetch(f"/series/{series_id}", {}).get("data") or {})
        recorded[request_key(f"/series/{series_id}", {})] = {"data": {
            "id": data.get("id"), "name": data.get("name"), "year": data.get("year"),
            "image": data.get("image"), "originalLanguage": data.get("originalLanguage"),
            "aliases": [a for a in (data.get("aliases") or []) if a.get("language") in ("jpn", LANGUAGE)],
        }}
        translated = fetch(f"/series/{series_id}/translations/{LANGUAGE}", {}).get("data") or {}
        recorded[request_key(f"/series/{series_id}/translations/{LANGUAGE}", {})] = {"data": {
            "name": translated.get("name"), "overview": (translated.get("overview") or "")[:200],
            "aliases": translated.get("aliases") or [],
        }}
        print(f"series  {series_id}")

    blob = json.dumps(recorded, indent=1, ensure_ascii=False)
    if key in blob or token in blob:
        print("refusing to write: a secret leaked into the payload", file=sys.stderr)
        return 3
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "responses.json"
    target.write_text(blob, encoding="utf-8")
    print(f"\nwrote {target}")
    print("Now run: python -m pytest tests/test_tvdb.py -q")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
