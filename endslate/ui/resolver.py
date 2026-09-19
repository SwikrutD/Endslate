"""Glue between the planner's matcher hook, TMDB and what you have already decided."""
from __future__ import annotations

from typing import Callable, Optional

from endslate.decisions import Decisions
from endslate.models import Confidence, Item, Metadata


class Resolver:
    """Callable the planner uses to turn parses into answers.

    Anything you resolved by hand, in this session or any previous one, wins over
    what the provider says. That is the point: a decision made once stays made.
    """

    def __init__(self, tmdb=None, decisions: Optional[Decisions] = None):
        self.tmdb = tmdb
        self.decisions = decisions if decisions is not None else Decisions()
        self.applied = 0

    def __call__(self, items: list[Item], progress: Optional[Callable] = None) -> None:
        known = [item for item in items if self.decisions.lookup(item) is not None]
        unknown = [item for item in items if self.decisions.lookup(item) is None]

        if self.tmdb is not None:
            self.tmdb.match_all(unknown, progress=progress)
        else:
            for item in unknown:
                item.confidence = offline_confidence(item)

        self.applied = 0
        for item in known:
            self._apply(item, self.decisions.lookup(item))
            self.applied += 1

    def _apply(self, item: Item, decision) -> None:
        item.meta = Metadata(
            title=decision.title,
            year=decision.year,
            tmdb_id=decision.tmdb_id,
            provider="remembered",
        )
        item.confidence = Confidence.HIGH
        item.note = "you set this earlier"
        if item.is_tv and self.tmdb is not None and decision.tmdb_id and item.parsed.season is not None:
            titles = self.tmdb.season_episodes(decision.tmdb_id, item.parsed.season)
            found = titles.get(item.parsed.episode or -1, "")
            if found:
                item.meta.episode_title = found
        if item.is_tv and not item.meta.episode_title:
            item.meta.episode_title = item.parsed.episode_title


def offline_confidence(item: Item) -> Confidence:
    if not item.parsed.title:
        return Confidence.NONE
    if item.is_tv:
        if item.parsed.season is not None and item.parsed.episode is not None:
            return Confidence.HIGH
        return Confidence.LOW
    return Confidence.HIGH if item.parsed.year else Confidence.LOW


# Kept so older call sites and tests keep working.
_offline = offline_confidence
