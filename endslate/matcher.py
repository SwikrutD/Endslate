"""Confirm a parse against TMDB.

The parser produces a search key. This turns that into an answer, or into a list
of candidates for the Needs you queue. It never invents a match: below the fuzzy
threshold an item stays unplanned.
"""
from __future__ import annotations

import difflib
import re
import threading
import time
from collections import deque
from typing import Callable, Iterable, Optional

from endslate.cache import Cache
from endslate.config import cache_path
from endslate.models import Candidate, Confidence, Item, Metadata

API = "https://api.themoviedb.org/3"
RATE_LIMIT = 40
RATE_WINDOW = 10.0
TIMEOUT = 15

_ARTICLE_RE = re.compile(r"^(the|a|an)\s+", re.I)


def normalize_title(title: str) -> str:
    out = title.lower().replace("&", "and")
    out = re.sub(r"[^a-z0-9]+", " ", out).strip()
    out = _ARTICLE_RE.sub("", out)
    return out


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()


class RateLimiter:
    def __init__(self, limit: int = RATE_LIMIT, window: float = RATE_WINDOW):
        self.limit = limit
        self.window = window
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            while self._calls and now - self._calls[0] > self.window:
                self._calls.popleft()
            if len(self._calls) >= self.limit:
                sleep_for = self.window - (now - self._calls[0])
                if sleep_for > 0:
                    time.sleep(sleep_for)
                self._calls.clear()
            self._calls.append(time.monotonic())


class TmdbError(RuntimeError):
    pass


class TmdbMatcher:
    def __init__(
        self,
        api_key: str,
        language: str = "en-US",
        fuzzy_threshold: float = 0.85,
        cache: Optional[Cache] = None,
        session=None,
    ):
        self.api_key = api_key
        self.language = language
        self.fuzzy_threshold = fuzzy_threshold
        self.cache = cache if cache is not None else Cache(cache_path())
        self.limiter = RateLimiter()
        self._session = session
        self.offline_reason = ""
        self.lookups = 0
        self.answered = 0

    # ---------------------------------------------------------------- transport

    def _client(self):
        if self._session is None:
            import requests

            self._session = requests.Session()
        return self._session

    def _get(self, path: str, **params) -> Optional[dict]:
        key = path + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items())) + f"&lang={self.language}"
        self.lookups += 1
        cached = self.cache.get(key)
        if cached is not None:
            self.answered += 1
            return cached
        if not self.api_key:
            return None
        self.limiter.wait()
        query = dict(params)
        query["api_key"] = self.api_key
        query["language"] = self.language
        try:
            response = self._client().get(f"{API}{path}", params=query, timeout=TIMEOUT)
        except Exception as exc:  # network down, DNS, proxy
            self.offline_reason = str(exc)
            return None
        if response.status_code == 401:
            raise TmdbError("TMDB rejected the API key")
        if response.status_code == 429:
            time.sleep(2)
            return self._get(path, **params)
        if response.status_code >= 400:
            self.offline_reason = f"HTTP {response.status_code}"
            return None
        data = response.json()
        self.cache.put(key, data)
        self.answered += 1
        return data

    # ------------------------------------------------------------------ movies

    def search_movie(self, title: str, year: Optional[int]) -> list[Candidate]:
        params = {"query": title}
        if year:
            params["year"] = year
        data = self._get("/search/movie", **params)
        if data is None and year:
            data = self._get("/search/movie", query=title)
        if not data:
            return []
        out = []
        for row in data.get("results", [])[:10]:
            release = (row.get("release_date") or "")[:4]
            out.append(
                Candidate(
                    title=row.get("title") or row.get("original_title") or "",
                    year=int(release) if release.isdigit() else None,
                    tmdb_id=row.get("id", 0),
                    overview=(row.get("overview") or "")[:200],
                    poster_path=row.get("poster_path") or "",
                )
            )
        return out

    # --------------------------------------------------------------------- tv

    def search_show(self, name: str, year: Optional[int]) -> list[Candidate]:
        params = {"query": name}
        if year:
            params["first_air_date_year"] = year
        data = self._get("/search/tv", **params)
        if data is None and year:
            data = self._get("/search/tv", query=name)
        if not data:
            return []
        out = []
        for row in data.get("results", [])[:10]:
            first = (row.get("first_air_date") or "")[:4]
            out.append(
                Candidate(
                    title=row.get("name") or row.get("original_name") or "",
                    year=int(first) if first.isdigit() else None,
                    tmdb_id=row.get("id", 0),
                    overview=(row.get("overview") or "")[:200],
                    poster_path=row.get("poster_path") or "",
                )
            )
        return out

    def season_episodes(self, show_id: int, season: int) -> dict[int, str]:
        data = self._get(f"/tv/{show_id}/season/{season}")
        if not data:
            return {}
        out = {}
        for row in data.get("episodes", []):
            number = row.get("episode_number")
            name = row.get("name") or ""
            if number is not None:
                out[int(number)] = name
        return out

    @property
    def unreachable(self) -> bool:
        """True once a lookup has failed and nothing has answered.

        Without this a network outage silently pushes every title into Needs you,
        which looks like the matcher deciding rather than the network failing.
        """
        return bool(self.api_key) and bool(self.offline_reason) and self.answered == 0

    # ---------------------------------------------------------------- scoring

    def _score(self, guess_title: str, guess_year: Optional[int], candidate: Candidate) -> float:
        """Title similarity plus a year bonus, deliberately uncapped.

        Capping at 1.0 threw the year away exactly when it mattered: two films
        called The Witch, one from 2015 and one from 2016, both scored 1.0, so
        the wrong year could sort first and the item fell into Needs you.
        """
        score = similarity(guess_title, candidate.title)
        if guess_year and candidate.year:
            if guess_year == candidate.year:
                score += 0.15
            elif abs(guess_year - candidate.year) == 1:
                score += 0.05
            else:
                score -= 0.20
        return round(score, 4)

    def _decide(self, item: Item, candidates: list[Candidate], guess_title: str, guess_year: Optional[int]):
        for candidate in candidates:
            candidate.score = self._score(guess_title, guess_year, candidate)
        candidates.sort(
            key=lambda c: (bool(guess_year and c.year == guess_year), c.score),
            reverse=True,
        )
        item.candidates = candidates[:8]
        if not candidates:
            item.confidence = Confidence.LOW
            item.note = "no TMDB result"
            return None
        best = candidates[0]
        exact = normalize_title(best.title) == normalize_title(guess_title)
        runner_up = candidates[1].score if len(candidates) > 1 else 0.0
        clear = best.score - runner_up >= 0.10 or len(candidates) == 1

        if exact and guess_year and best.year == guess_year:
            item.confidence = Confidence.HIGH
        elif exact and not guess_year and clear:
            item.confidence = Confidence.HIGH
        elif best.score >= self.fuzzy_threshold and clear:
            item.confidence = Confidence.MEDIUM
            item.note = f"matched '{best.label}' at {best.score:.2f}"
        else:
            item.confidence = Confidence.LOW
            item.note = f"{len(candidates)} plausible matches, best '{best.label}' at {best.score:.2f}"
            return None
        return best

    # ------------------------------------------------------------------ driver

    def match_all(self, items: list[Item], progress: Optional[Callable[[str, int, int], None]] = None) -> None:
        movies = [i for i in items if not i.is_tv]
        episodes = [i for i in items if i.is_tv]
        total = len(items)
        done = 0

        movie_cache: dict[tuple, Optional[Candidate]] = {}
        for item in movies:
            done += 1
            if progress and done % 5 == 0:
                progress("matching", done, total)
            if not item.parsed.title:
                item.confidence = Confidence.NONE
                continue
            if self.unreachable:
                item.confidence = _fallback_confidence(item)
                item.note = f"TMDB unreachable ({self.offline_reason}), used the filename"
                continue
            key = (normalize_title(item.parsed.title), item.parsed.year)
            if key in movie_cache:
                best = movie_cache[key]
                if best is None:
                    item.confidence = Confidence.LOW
                    item.note = "no confident TMDB match"
                    continue
            else:
                candidates = self.search_movie(item.parsed.title, item.parsed.year)
                if not candidates and (not self.api_key or self.unreachable):
                    item.confidence = _fallback_confidence(item)
                    if self.unreachable:
                        item.note = f"TMDB unreachable ({self.offline_reason}), used the filename"
                    continue
                best = self._decide(item, candidates, item.parsed.title, item.parsed.year)
                movie_cache[key] = best
            if best is not None:
                item.meta = Metadata(title=best.title, year=best.year, tmdb_id=best.tmdb_id, provider="tmdb")
                if item.confidence not in (Confidence.HIGH, Confidence.MEDIUM):
                    item.confidence = Confidence.MEDIUM

        shows: dict[str, list[Item]] = {}
        for item in episodes:
            shows.setdefault(item.show_hint or item.parsed.title, []).append(item)

        for show_name, group in shows.items():
            done += len(group)
            if progress:
                progress("matching", min(done, total), total)
            sample = group[0]
            if self.unreachable:
                for item in group:
                    item.confidence = _fallback_confidence(item)
                    item.note = f"TMDB unreachable ({self.offline_reason}), used the filename"
                continue
            candidates = self.search_show(show_name, sample.parsed.year)
            if not candidates and (not self.api_key or self.unreachable):
                for item in group:
                    item.confidence = _fallback_confidence(item)
                    if self.unreachable:
                        item.note = f"TMDB unreachable ({self.offline_reason}), used the filename"
                continue
            best = self._decide(sample, candidates, show_name, sample.parsed.year)
            if best is None:
                for item in group:
                    item.confidence = Confidence.LOW
                    item.candidates = sample.candidates
                    item.note = sample.note
                continue
            seasons: dict[int, dict[int, str]] = {}
            for item in group:
                item.candidates = sample.candidates
                season = item.parsed.season
                if season is None or item.parsed.episode is None:
                    item.confidence = Confidence.LOW
                    item.note = "no season or episode number"
                    continue
                if season not in seasons:
                    seasons[season] = self.season_episodes(best.tmdb_id, season)
                episode_title = seasons[season].get(item.parsed.episode, "")
                item.meta = Metadata(
                    title=best.title,
                    year=best.year,
                    episode_title=episode_title or item.parsed.episode_title,
                    tmdb_id=best.tmdb_id,
                    provider="tmdb",
                )
                item.confidence = sample.confidence if sample.confidence != Confidence.LOW else Confidence.MEDIUM
                if not episode_title:
                    item.note = "episode title not in TMDB, kept the one from the filename"


def _fallback_confidence(item: Item) -> Confidence:
    if not item.parsed.title:
        return Confidence.NONE
    if item.is_tv:
        return Confidence.HIGH if item.parsed.season is not None and item.parsed.episode is not None else Confidence.LOW
    return Confidence.HIGH if item.parsed.year else Confidence.LOW
