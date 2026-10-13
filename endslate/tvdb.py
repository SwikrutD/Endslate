"""Confirm anime against TheTVDB.

TMDB numbers anime by season, the way most western shows are numbered. Fansub
releases count from the first episode instead ("[SubsPlease] One Piece - 1085"),
and TheTVDB is the source that publishes the absolute order turning that count
into a season and an episode. Jellyfin's own anime support leans on it for the
same reason.

This is TmdbMatcher with a different transport. The scoring and the refusal to
guess are inherited unchanged, so a title below the threshold, or a tie, still
goes to Needs you. Two signals are added, both from the release itself: a
fansub file is anime, so a show whose original language is Japanese, Chinese or
Korean outranks a western one of the same name; and a folder that already
carries [tvdbid-N] is that show, no search needed.
"""
from __future__ import annotations

import re
import time
from typing import Callable, Optional

from endslate.cache import Cache
from endslate.matcher import (
    MAX_RETRIES,
    TIMEOUT,
    TmdbError,
    TmdbMatcher,
    normalize_title,
    offline_confidence,
)
from endslate.models import Candidate, Confidence, Item, Metadata

API = "https://api4.thetvdb.com/v4"
MAX_PAGES = 40
ANIME_LANGUAGES = {"jpn", "zho", "chi", "kor", "cmn", "yue"}
ANIME_BONUS = 0.12

# TheTVDB wants three-letter codes. The metadata language setting is TMDB's
# "en-US" form, so it is translated rather than asked for twice.
_LANGUAGES = {
    "en": "eng", "de": "deu", "fr": "fra", "es": "spa", "it": "ita", "pt": "por",
    "nl": "nld", "sv": "swe", "da": "dan", "no": "nor", "fi": "fin", "pl": "pol",
    "ru": "rus", "ja": "jpn", "ko": "kor", "zh": "zho", "tr": "tur", "cs": "ces",
    "hu": "hun", "el": "ell", "he": "heb", "ar": "ara", "hi": "hin", "th": "tha",
}

_YEAR_SUFFIX = re.compile(r"\s*\((?:19|20)\d{2}\)\s*$")
_LATIN = re.compile(r"[A-Za-z]")


def tvdb_language(metadata_language: str) -> str:
    code = (metadata_language or "en").split("-")[0].lower()
    return _LANGUAGES.get(code, "eng")


class TvdbError(TmdbError):
    pass


def _clean_name(name: str) -> str:
    """"ONE PIECE (2023)" is how TheTVDB tells two shows apart. The year
    belongs in the year field, or the folder reads ONE PIECE (2023) (2023)."""
    return _YEAR_SUFFIX.sub("", name or "").strip()


def _readable(names: list[str]) -> str:
    """The first name a Windows folder and a person can both read."""
    for name in names:
        if name and _LATIN.search(name):
            return name
    return next((n for n in names if n), "")


class TvdbMatcher(TmdbMatcher):
    provider_name = "TheTVDB"
    provider_key = "tvdb"

    def __init__(
        self,
        api_key: str,
        language: str = "en-US",
        fuzzy_threshold: float = 0.85,
        cache: Optional[Cache] = None,
        session=None,
        pin: str = "",
    ):
        super().__init__(api_key, language=language, fuzzy_threshold=fuzzy_threshold,
                         cache=cache, session=session)
        self.tvdb_language = tvdb_language(language)
        self.pin = pin.strip()
        self._token: Optional[str] = None
        self._indexes: dict[int, tuple[dict, dict]] = {}

    # ---------------------------------------------------------------- transport

    def _login(self) -> Optional[str]:
        body = {"apikey": self.api_key}
        if self.pin:
            body["pin"] = self.pin
        self.limiter.wait()
        try:
            response = self._client().post(f"{API}/login", json=body, timeout=TIMEOUT)
        except Exception as exc:  # network down, DNS, proxy
            self.offline_reason = str(exc)
            return None
        if response.status_code == 401:
            raise TvdbError("TheTVDB rejected the API key")
        if response.status_code >= 400:
            self.offline_reason = f"HTTP {response.status_code} at login"
            return None
        try:
            self._token = response.json()["data"]["token"]
        except (KeyError, TypeError, ValueError):
            self.offline_reason = "TheTVDB login returned no token"
            return None
        return self._token

    def _get(self, path: str, _attempt: int = 0, **params) -> Optional[dict]:
        key = "tvdb:" + path + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        if _attempt == 0:
            self.lookups += 1
            cached = self.cache.get(key)
            if cached is not None:
                self.answered += 1
                return cached
        if not self.api_key:
            return None
        if self._token is None and self._login() is None:
            return None
        self.limiter.wait()
        try:
            response = self._client().get(
                f"{API}{path}",
                params=params,
                headers={"Authorization": f"Bearer {self._token}", "Accept": "application/json"},
                timeout=TIMEOUT,
            )
        except Exception as exc:
            self.offline_reason = str(exc)
            return None
        if response.status_code == 401:
            # The token lasts a month. A stale one gets one fresh login.
            self._token = None
            if _attempt >= 1:
                raise TvdbError("TheTVDB rejected the API key")
            return self._get(path, _attempt=_attempt + 1, **params)
        if response.status_code == 429:
            if _attempt >= MAX_RETRIES:
                self.offline_reason = "HTTP 429, rate limited"
                return None
            time.sleep(2 * (_attempt + 1))
            return self._get(path, _attempt=_attempt + 1, **params)
        if response.status_code == 404:
            # Not there is an answer, not an outage.
            self.answered += 1
            return {}
        if response.status_code >= 400:
            self.offline_reason = f"HTTP {response.status_code}"
            return None
        data = response.json()
        self.cache.put(key, data)
        self.answered += 1
        return data

    # ------------------------------------------------------------------ search

    def _candidate(self, row: dict) -> Optional[Candidate]:
        raw_id = str(row.get("tvdb_id") or row.get("id") or "").replace("series-", "")
        if not raw_id.isdigit():
            return None
        translations = row.get("translations") or {}
        overviews = row.get("overviews") or {}
        original = row.get("name") or ""
        names = [translations.get(self.tvdb_language), translations.get("eng"), original]
        names += [a for a in (row.get("aliases") or []) if isinstance(a, str)]
        names = [_clean_name(n) for n in names if n]
        title = _readable(names)
        aliases: list[str] = []
        for name in names:
            # A name with no Latin letters normalises to nothing, and two
            # nothings compare equal: every Japanese title would be an exact match.
            if name != title and name not in aliases and normalize_title(name):
                aliases.append(name)
        year = str(row.get("year") or "")[:4]
        return Candidate(
            title=title,
            year=int(year) if year.isdigit() else None,
            tmdb_id=0,
            tvdb_id=int(raw_id),
            overview=(overviews.get(self.tvdb_language) or overviews.get("eng") or row.get("overview") or "")[:200],
            poster_path=row.get("image_url") or row.get("thumbnail") or "",
            aliases=aliases,
            origin_language=(row.get("primary_language") or "").lower(),
        )

    def search_show(self, name: str, year: Optional[int]) -> list[Candidate]:
        params = {"query": name, "type": "series"}
        if year:
            params["year"] = year
        data = self._get("/search", **params)
        if not (data or {}).get("data") and year:
            data = self._get("/search", query=name, type="series")
        if not data:
            return []
        out = []
        for row in (data.get("data") or [])[:10]:
            candidate = self._candidate(row)
            if candidate is not None:
                out.append(candidate)
        return out

    def search_movie(self, title: str, year: Optional[int]) -> list[Candidate]:
        return []

    def series(self, tvdb_id: int) -> Optional[Candidate]:
        """One show by id, for a folder that already names it."""
        data = self._get(f"/series/{tvdb_id}")
        row = (data or {}).get("data")
        if not row:
            return None
        translated = (self._get(f"/series/{tvdb_id}/translations/{self.tvdb_language}") or {}).get("data") or {}
        aliases = [a.get("name") for a in (row.get("aliases") or []) if isinstance(a, dict)]
        aliases += [a for a in (translated.get("aliases") or []) if isinstance(a, str)]
        return self._candidate({
            "tvdb_id": row.get("id"),
            "name": row.get("name"),
            "year": row.get("year"),
            "image_url": row.get("image"),
            "translations": {self.tvdb_language: translated.get("name")},
            "overviews": {self.tvdb_language: translated.get("overview")},
            "aliases": aliases,
            "primary_language": row.get("originalLanguage"),
        })

    # ---------------------------------------------------------------- episodes

    def _episodes(self, tvdb_id: int) -> list[dict]:
        out: list[dict] = []
        for path in (f"/series/{tvdb_id}/episodes/default/{self.tvdb_language}",
                     f"/series/{tvdb_id}/episodes/default"):
            for page in range(MAX_PAGES):
                data = self._get(path, page=page)
                payload = (data or {}).get("data") or {}
                episodes = payload.get("episodes") or []
                out.extend(episodes)
                if not episodes or not ((data or {}).get("links") or {}).get("next"):
                    break
            if out:
                break
        return out

    def episode_index(self, tvdb_id: int) -> tuple[dict, dict]:
        """(season, episode) -> title, and absolute number -> (season, episode, title).

        Specials (season 0) are left out of the absolute count, as TheTVDB does.
        When it publishes no absolute numbers at all they are counted in order,
        which is what an absolute number means.
        """
        if tvdb_id in self._indexes:
            return self._indexes[tvdb_id]
        regular = [
            e for e in self._episodes(tvdb_id)
            if (e.get("seasonNumber") or 0) > 0 and e.get("number") is not None
        ]
        regular.sort(key=lambda e: (e["seasonNumber"], e["number"]))
        by_episode = {(int(e["seasonNumber"]), int(e["number"])): e.get("name") or "" for e in regular}
        by_absolute: dict[int, tuple[int, int, str]] = {}
        numbered = [e for e in regular if (e.get("absoluteNumber") or 0) > 0]
        if numbered:
            for e in numbered:
                by_absolute.setdefault(int(e["absoluteNumber"]),
                                       (int(e["seasonNumber"]), int(e["number"]), e.get("name") or ""))
        else:
            for index, e in enumerate(regular, start=1):
                by_absolute[index] = (int(e["seasonNumber"]), int(e["number"]), e.get("name") or "")
        self._indexes[tvdb_id] = (by_episode, by_absolute)
        return by_episode, by_absolute

    def season_episodes(self, show_id: int, season: int) -> dict[int, str]:
        by_episode, _ = self.episode_index(show_id)
        return {number: name for (s, number), name in by_episode.items() if s == season}

    def place(self, item: Item, by_episode: dict, by_absolute: dict) -> tuple[bool, str, str]:
        """Give an episode its season and number. Returns (placed, title, note).

        Sets the parse's season and episode when TheTVDB settles them. Never
        picks between two readings: a number that fits neither is left alone.
        """
        p = item.parsed
        if p.season is not None and p.episode is not None:
            title = by_episode.get((p.season, p.episode), "")
            note = "" if title or not by_episode else (
                f"S{p.season:02}E{p.episode:02} is not on TheTVDB, kept the numbers from the filename"
            )
            return True, title, note
        if p.absolute is None:
            return False, "", "no episode number"
        hit = by_absolute.get(p.absolute)
        if p.season is not None:
            # "Season 2/Frieren - 05": the fifth of season two, or the fifth
            # overall. Only one of the two may fit.
            relative = (p.season, p.absolute) in by_episode
            counted = hit is not None and hit[0] == p.season
            if counted and not relative:
                p.episode = hit[1]
                return True, hit[2], f"episode {p.absolute} counted from the start is S{hit[0]:02}E{hit[1]:02}"
            if relative and not counted:
                p.episode = p.absolute
                return True, by_episode[(p.season, p.absolute)], ""
            if relative and counted and hit[1] == p.absolute:
                p.episode = p.absolute
                return True, hit[2], ""
            return False, "", (
                f"episode {p.absolute} in a season {p.season} folder fits TheTVDB both ways or neither"
            )
        if hit is None:
            return False, "", f"episode {p.absolute} is not on TheTVDB yet"
        p.season, p.episode = hit[0], hit[1]
        return True, hit[2], f"episode {p.absolute} counted from the start is S{hit[0]:02}E{hit[1]:02}"

    # ---------------------------------------------------------------- scoring

    def _score(self, guess_title: str, guess_year: Optional[int], candidate: Candidate) -> float:
        score = super()._score(guess_title, guess_year, candidate)
        if candidate.origin_language in ANIME_LANGUAGES:
            # Everything handed to this matcher is anime. ONE PIECE (2023) and
            # One Piece (1999) are both exactly "One Piece"; only one is anime.
            score += ANIME_BONUS
        return round(score, 4)

    def _narrow(self, tied: list[Candidate]) -> list[Candidate]:
        # The live-action ONE PIECE lists "One Piece" among its names, so the
        # letter-for-letter tie-break found two. Only one of them is anime.
        anime = [c for c in tied if c.origin_language in ANIME_LANGUAGES]
        return anime or tied

    # ------------------------------------------------------------------ driver

    def match_all(self, items: list[Item], progress: Optional[Callable[[str, int, int], None]] = None) -> None:
        shows: dict[str, list[Item]] = {}
        for item in items:
            shows.setdefault(item.show_hint or item.parsed.title, []).append(item)

        total = len(items)
        done = 0
        for show_name, group in shows.items():
            done += len(group)
            if progress:
                progress("matching anime", min(done, total), total)
            sample = group[0]
            if self.unreachable:
                self._fallback(group)
                continue

            best = None
            pinned = next((i.parsed.tvdb_id for i in group if i.parsed.tvdb_id), None)
            if pinned:
                best = self.series(pinned)
                if best is not None:
                    sample.candidates = [best]
                    sample.confidence = Confidence.HIGH
                    sample.note = ""
            if best is None:
                query = sample.parsed.title or show_name
                candidates = self.search_show(query, sample.parsed.year)
                if not candidates and (not self.api_key or self.unreachable):
                    self._fallback(group)
                    continue
                best = self._decide(sample, candidates, query, sample.parsed.year)
            if best is None:
                for item in group:
                    item.confidence = Confidence.LOW
                    item.candidates = sample.candidates
                    item.note = sample.note
                continue

            by_episode, by_absolute = self.episode_index(best.tvdb_id)
            confidence = sample.confidence if sample.confidence != Confidence.LOW else Confidence.MEDIUM
            show_note = sample.note
            for item in group:
                item.candidates = sample.candidates
                placed, episode_title, note = self.place(item, by_episode, by_absolute)
                item.meta = Metadata(
                    title=best.title,
                    year=best.year,
                    episode_title=episode_title or item.parsed.episode_title,
                    tvdb_id=best.tvdb_id,
                    provider="tvdb",
                )
                if not placed:
                    item.confidence = Confidence.LOW
                    item.note = note
                    continue
                item.confidence = confidence
                item.note = "; ".join(n for n in (show_note if confidence is Confidence.MEDIUM else "", note) if n)

    def _fallback(self, group: list[Item]) -> None:
        for item in group:
            item.confidence = offline_confidence(item)
            if self.unreachable:
                item.note = f"TheTVDB unreachable ({self.offline_reason}), used the filename"
