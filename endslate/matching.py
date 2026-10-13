"""Which provider answers for which item, and what you have already decided.

Films and western shows go to TMDB. Anime goes to TheTVDB, which is the one
that knows absolute episode numbers. Without a TheTVDB key anime falls back to
TMDB, which can still place anything named S01E05, and whatever is numbered
from the start of the show waits in Needs you rather than being guessed.
"""
from __future__ import annotations

from typing import Callable, Optional

from endslate.decisions import Decisions
from endslate.matcher import offline_confidence
from endslate.models import Confidence, Item, Metadata

NO_TVDB_NOTE = (
    "episode {n} is counted from the start of the show. Add a TheTVDB key in "
    "Settings to place it in a season"
)


def match_items(items: list[Item], tmdb=None, tvdb=None,
                progress: Optional[Callable[[str, int, int], None]] = None) -> None:
    anime = [item for item in items if item.is_tv and item.is_anime]
    others = [item for item in items if not (item.is_tv and item.is_anime)]
    if tvdb is not None and anime:
        tvdb.match_all(anime, progress=progress)
    else:
        others = others + anime

    if tmdb is not None and others:
        tmdb.match_all(others, progress=progress)
    else:
        for item in others:
            item.confidence = offline_confidence(item)

    if tvdb is None:
        for item in anime:
            if item.parsed.absolute is not None and not item.parsed.is_episode:
                item.confidence = Confidence.LOW
                item.note = NO_TVDB_NOTE.format(n=item.parsed.absolute)


class Resolver:
    """Callable the planner uses to turn parses into answers.

    Anything you resolved by hand, in this session or any previous one, wins over
    what the provider says. That is the point: a decision made once stays made.
    """

    def __init__(self, tmdb=None, decisions: Optional[Decisions] = None, tvdb=None):
        self.tmdb = tmdb
        self.tvdb = tvdb
        self.decisions = decisions if decisions is not None else Decisions()
        self.applied = 0

    def __call__(self, items: list[Item], progress: Optional[Callable] = None) -> None:
        known = [item for item in items if self.decisions.lookup(item) is not None]
        unknown = [item for item in items if self.decisions.lookup(item) is None]

        match_items(unknown, tmdb=self.tmdb, tvdb=self.tvdb, progress=progress)

        self.applied = 0
        for item in known:
            self._apply(item, self.decisions.lookup(item))
            self.applied += 1

    def _apply(self, item: Item, decision) -> None:
        item.meta = Metadata(
            title=decision.title,
            year=decision.year,
            tmdb_id=decision.tmdb_id,
            tvdb_id=getattr(decision, "tvdb_id", None),
            provider="remembered",
        )
        item.confidence = Confidence.HIGH
        item.note = "you set this earlier"
        if item.is_tv and self.tvdb is not None and item.meta.tvdb_id:
            by_episode, by_absolute = self.tvdb.episode_index(item.meta.tvdb_id)
            placed, title, note = self.tvdb.place(item, by_episode, by_absolute)
            if not placed:
                item.confidence = Confidence.LOW
                item.note = f"you set the show earlier, but {note}"
            elif title:
                item.meta.episode_title = title
        elif item.is_tv and self.tmdb is not None and decision.tmdb_id and item.parsed.season is not None:
            titles = self.tmdb.season_episodes(decision.tmdb_id, item.parsed.season)
            found = titles.get(item.parsed.episode or -1, "")
            if found:
                item.meta.episode_title = found
        if item.is_tv and not item.meta.episode_title:
            item.meta.episode_title = item.parsed.episode_title
