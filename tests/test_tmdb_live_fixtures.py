"""Drive the matcher with responses TMDB actually returned.

Skipped until someone records them (scripts/record_tmdb.py). A stub written from
assumptions agrees with those assumptions, which is how the two films called The
Witch got through. These are the real thing, replayed offline.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from endslate.cache import Cache
from endslate.matcher import TmdbMatcher
from endslate.models import Confidence

FIXTURE = Path(__file__).parent / "fixtures" / "tmdb" / "responses.json"
pytestmark = pytest.mark.skipif(
    not FIXTURE.exists(),
    reason="no recorded TMDB responses yet, run scripts/record_tmdb.py",
)


class ReplayResponse:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload

    def json(self):
        return self._payload


class ReplaySession:
    """Answers from the recording, and notes anything that was not recorded."""

    def __init__(self, recorded: dict):
        self.recorded = recorded
        self.misses: list[str] = []

    def get(self, url, params=None, timeout=None):
        params = params or {}
        if "/search/movie" in url:
            key = f"{params.get('query')}|{params.get('year') or ''}"
            results = self.recorded["movies"].get(key)
            if results is None:
                self.misses.append(f"movie {key}")
                return ReplayResponse({"results": []})
            return ReplayResponse({"results": results})
        if "/search/tv" in url:
            key = f"{params.get('query')}|{params.get('first_air_date_year') or ''}"
            results = self.recorded["shows"].get(key)
            if results is None:
                self.misses.append(f"show {key}")
                return ReplayResponse({"results": []})
            return ReplayResponse({"results": results})
        if "/season/" in url:
            season = url.rsplit("/", 1)[-1]
            show_id = url.split("/tv/")[1].split("/")[0]
            episodes = self.recorded["seasons"].get(f"{show_id}|{season}", {})
            return ReplayResponse(
                {"episodes": [{"episode_number": int(n), "name": t} for n, t in episodes.items()]}
            )
        return ReplayResponse({})


@pytest.fixture(scope="module")
def recorded():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def matcher(recorded, tmp_path):
    return TmdbMatcher(
        "recorded", cache=Cache(tmp_path / "c.sqlite"), session=ReplaySession(recorded)
    )


def movie(title, year=None):
    from tests.test_matcher import movie_item

    return movie_item(title, year)


def episode(show, season, number):
    from tests.test_matcher import episode_item

    return episode_item(show, season, number)


@pytest.mark.parametrize(
    "title,year,expected_year",
    [
        ("Fight Club", 1999, 1999),
        ("The Witch", 2015, 2015),
        ("Dune - Part One", 2021, 2021),
        ("WALL-E", 2008, 2008),
        ("Angry Birds Movie", 2016, 2016),
        ("Demon Slayer Kimetsu No Yaiba Infinity Castle", 2025, 2025),
    ],
)
def test_real_results_resolve_to_the_right_year(matcher, title, year, expected_year):
    item = movie(title, year)
    matcher.match_all([item])
    assert item.confidence in (Confidence.HIGH, Confidence.MEDIUM), item.note
    assert item.meta.year == expected_year


@pytest.mark.parametrize("title", ["Beauty And The Beast", "Doctor Strange"])
def test_a_title_with_two_real_films_asks_rather_than_guesses(matcher, title):
    item = movie(title)
    matcher.match_all([item])
    assert item.confidence is Confidence.LOW
    assert len(item.candidates) > 1


def test_episode_titles_come_back_from_the_recording(matcher):
    items = [episode("Dark", 1, 1), episode("Dark", 1, 2)]
    matcher.match_all(items)
    assert all(item.meta.episode_title for item in items)
    assert items[0].meta.episode_title != items[1].meta.episode_title


def test_every_query_the_matcher_makes_was_recorded(matcher):
    items = [movie("Fight Club", 1999), episode("The 100", 3, 1)]
    matcher.match_all(items)
    assert not matcher._session.misses, matcher._session.misses
