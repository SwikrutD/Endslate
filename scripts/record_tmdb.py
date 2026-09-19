"""Record real TMDB responses as test fixtures.

Every matcher test in the suite runs against a stub written from assumptions,
which is exactly the blind spot that let the two films called The Witch through.
Run this once on a machine that can reach TMDB and the suite replays real
answers for ever after, still offline.

    python scripts/record_tmdb.py

The key is read from %LOCALAPPDATA%\\Endslate\\config.json, or from TMDB_API_KEY.
It is never written to the fixtures: only response bodies are saved.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from endslate.config import load_config  # noqa: E402
from endslate.matcher import API  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "tmdb"

# Drawn from the real library: the ambiguous, the obscure and the easy.
MOVIES = [
    ("Fight Club", 1999),
    ("The Witch", 2015),
    ("Beauty And The Beast", None),
    ("Doctor Strange", None),
    ("Rush Hour", None),
    ("Now You See Me", None),
    ("Black Panther", None),
    ("Death on the Nile", None),
    ("Nerve", None),
    ("Mr Bean Man vs. Baby", None),
    ("Indiana Jones Raiders Lost Ark", None),
    ("The Family Plan 2", None),
    ("Dune - Part One", 2021),
    ("My Big Fat Greek Wedding 2", 2016),
    ("Housefull 5", 2025),
    ("Sitaare Zameen Par", 2025),
    ("Demon Slayer Kimetsu No Yaiba Infinity Castle", 2025),
    ("Angry Birds Movie", 2016),
    ("WALL-E", 2008),
    ("IT", 2017),
]

SHOWS = [
    ("Dark", None),
    ("The 100", None),
    ("Modern Family", 2009),
    ("Gravity Falls", None),
    ("One Piece", None),
    ("Squid Game", None),
    ("Game of Thrones", 2011),
]

SEASONS = [
    ("Dark", 1),
    ("The 100", 3),
    ("Gravity Falls", 1),
    ("One Piece", 1),
    ("Squid Game", 3),
    ("Game of Thrones", 1),
    ("Modern Family", 5),
]


def fetch(session, key: str, path: str, params: dict) -> dict:
    query = dict(params)
    query["api_key"] = key
    query["language"] = "en-US"
    response = session.get(f"{API}{path}", params=query, timeout=20)
    response.raise_for_status()
    time.sleep(0.3)
    return response.json()


def trim_movie(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "title": row.get("title"),
        "original_title": row.get("original_title"),
        "release_date": row.get("release_date"),
        "overview": (row.get("overview") or "")[:200],
        "poster_path": row.get("poster_path"),
    }


def trim_show(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "original_name": row.get("original_name"),
        "first_air_date": row.get("first_air_date"),
        "overview": (row.get("overview") or "")[:200],
        "poster_path": row.get("poster_path"),
    }


def main() -> int:
    key = os.environ.get("TMDB_API_KEY") or load_config().tmdb_api_key
    if not key:
        print("No TMDB key. Put one in Settings, or set TMDB_API_KEY.", file=sys.stderr)
        return 2
    try:
        import requests
    except ImportError:
        print("pip install requests", file=sys.stderr)
        return 2

    session = requests.Session()
    OUT.mkdir(parents=True, exist_ok=True)
    recorded = {"movies": {}, "shows": {}, "seasons": {}}
    show_ids: dict[str, int] = {}

    for title, year in MOVIES:
        params = {"query": title}
        if year:
            params["year"] = year
        data = fetch(session, key, "/search/movie", params)
        results = [trim_movie(r) for r in data.get("results", [])[:10]]
        recorded["movies"][f"{title}|{year or ''}"] = results
        print(f"movie  {title:48} {len(results)} results")

    for name, year in SHOWS:
        params = {"query": name}
        if year:
            params["first_air_date_year"] = year
        data = fetch(session, key, "/search/tv", params)
        results = [trim_show(r) for r in data.get("results", [])[:10]]
        recorded["shows"][f"{name}|{year or ''}"] = results
        if results:
            show_ids[name] = results[0]["id"]
        print(f"show   {name:48} {len(results)} results")

    for name, season in SEASONS:
        show_id = show_ids.get(name)
        if not show_id:
            continue
        data = fetch(session, key, f"/tv/{show_id}/season/{season}", {})
        episodes = {
            str(e.get("episode_number")): e.get("name") or ""
            for e in data.get("episodes", [])
        }
        recorded["seasons"][f"{show_id}|{season}"] = episodes
        print(f"season {name} S{season:02}{'':38} {len(episodes)} episodes")

    blob = json.dumps(recorded, indent=2, ensure_ascii=False)
    if key in blob:
        print("refusing to write: the key leaked into the payload", file=sys.stderr)
        return 3
    target = OUT / "responses.json"
    target.write_text(blob, encoding="utf-8")
    print(f"\nwrote {target}")
    print("Now run: python -m pytest tests/test_tmdb_live_fixtures.py -q")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
