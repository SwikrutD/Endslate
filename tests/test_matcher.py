"""The matcher is tested against a stub TMDB so the suite never needs network."""
from pathlib import Path

import pytest

from endslate.cache import Cache
from endslate.matcher import TmdbMatcher, normalize_title, similarity
from endslate.models import Confidence, FileKind, Item, ParsedName, ScannedFile


class FakeResponse:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload

    def json(self):
        return self._payload


class FakeSession:
    """Answers the handful of endpoints the matcher uses."""

    def __init__(self, movies=None, shows=None, episodes=None):
        self.movies = movies or {}
        self.shows = shows or {}
        self.episodes = episodes or {}
        self.calls = []

    def get(self, url, params=None, timeout=None):
        params = params or {}
        self.calls.append((url, params.get("query")))
        if "/search/movie" in url:
            return FakeResponse({"results": self.movies.get(params.get("query"), [])})
        if "/search/tv" in url:
            return FakeResponse({"results": self.shows.get(params.get("query"), [])})
        if "/season/" in url:
            season = int(url.rsplit("/", 1)[-1])
            show_id = int(url.split("/tv/")[1].split("/")[0])
            payload = self.episodes.get((show_id, season), {})
            return FakeResponse({"episodes": [{"episode_number": n, "name": t} for n, t in payload.items()]})
        return FakeResponse({})


@pytest.fixture
def cache(tmp_path):
    return Cache(tmp_path / "cache.sqlite")


def movie_item(title, year=None):
    parsed = ParsedName(title=title, year=year)
    video = ScannedFile(path=Path(f"/library/Movies/{title}/{title}.mkv"), size=1, kind=FileKind.VIDEO)
    return Item(video=video, parsed=parsed)


def episode_item(show, season, episode, title=""):
    parsed = ParsedName(title=show, season=season, episode=episode, episode_title=title)
    video = ScannedFile(path=Path(f"/library/Shows/{show}/{show}.mkv"), size=1, kind=FileKind.VIDEO)
    return Item(video=video, is_tv=True, show_hint=show, parsed=parsed)


def test_exact_title_and_year_is_high_confidence(cache):
    session = FakeSession(movies={"Fight Club": [
        {"id": 550, "title": "Fight Club", "release_date": "1999-10-15"},
    ]})
    matcher = TmdbMatcher("key", cache=cache, session=session)
    item = movie_item("Fight Club", 1999)
    matcher.match_all([item])
    assert item.confidence is Confidence.HIGH
    assert item.meta.title == "Fight Club"
    assert item.meta.year == 1999


def test_two_plausible_matches_stay_low(cache):
    session = FakeSession(movies={"Beauty And The Beast": [
        {"id": 1, "title": "Beauty and the Beast", "release_date": "1991-11-22"},
        {"id": 2, "title": "Beauty and the Beast", "release_date": "2017-03-16"},
    ]})
    matcher = TmdbMatcher("key", cache=cache, session=session)
    item = movie_item("Beauty And The Beast")
    matcher.match_all([item])
    assert item.confidence is Confidence.LOW
    assert len(item.candidates) == 2


def test_year_less_title_with_one_match_resolves(cache):
    session = FakeSession(movies={"Rush Hour": [
        {"id": 3, "title": "Rush Hour", "release_date": "1998-09-18"},
    ]})
    matcher = TmdbMatcher("key", cache=cache, session=session)
    item = movie_item("Rush Hour")
    matcher.match_all([item])
    assert item.confidence is Confidence.HIGH
    assert item.meta.year == 1998


def test_episode_titles_come_from_the_provider(cache):
    session = FakeSession(
        shows={"Dark": [{"id": 70523, "name": "Dark", "first_air_date": "2017-12-01"}]},
        episodes={(70523, 1): {1: "Secrets", 2: "Lies"}},
    )
    matcher = TmdbMatcher("key", cache=cache, session=session)
    items = [episode_item("Dark", 1, 1), episode_item("Dark", 1, 2)]
    matcher.match_all(items)
    assert [i.episode_title for i in items] == ["Secrets", "Lies"]
    assert all(i.meta.year == 2017 for i in items)


def test_the_cache_stops_a_second_lookup(cache):
    session = FakeSession(movies={"Fight Club": [
        {"id": 550, "title": "Fight Club", "release_date": "1999-10-15"},
    ]})
    matcher = TmdbMatcher("key", cache=cache, session=session)
    matcher.match_all([movie_item("Fight Club", 1999)])
    first = len(session.calls)
    TmdbMatcher("key", cache=cache, session=session).match_all([movie_item("Fight Club", 1999)])
    assert len(session.calls) == first


def test_no_result_leaves_the_item_alone(cache):
    matcher = TmdbMatcher("key", cache=cache, session=FakeSession())
    item = movie_item("Indian Institute Of Zombies")
    matcher.match_all([item])
    assert item.confidence is Confidence.LOW
    assert item.meta.title == ""


def test_similarity_ignores_articles_and_punctuation():
    assert similarity("The Hangover Part Ii", "The Hangover Part II") == 1.0
    assert normalize_title("The 100") == "100"
