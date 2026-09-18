"""Glue between the planner's matcher hook, TMDB and the user's manual overrides."""
from __future__ import annotations

from typing import Callable, Optional

from endslate.models import Confidence, Item, Metadata


class Resolver:
    """Callable the planner uses to turn parses into answers."""

    def __init__(self, tmdb=None, overrides=None, show_overrides=None):
        self.tmdb = tmdb
        self.overrides: dict[str, dict] = overrides if overrides is not None else {}
        self.show_overrides: dict[str, dict] = show_overrides if show_overrides is not None else {}

    def __call__(self, items: list[Item], progress: Optional[Callable] = None) -> None:
        if self.tmdb is not None:
            self.tmdb.match_all(items, progress=progress)
        else:
            for item in items:
                item.confidence = _offline(item)
        self.apply_overrides(items)

    def apply_overrides(self, items: list[Item]) -> None:
        for item in items:
            data = self.overrides.get(str(item.video.path))
            if data is None and item.is_tv:
                data = self.show_overrides.get(item.show_hint)
            if data is None:
                continue
            item.meta = Metadata(
                title=data.get("title", item.title),
                year=data.get("year", item.year),
                episode_title=data.get("episode_title", item.meta.episode_title),
                tmdb_id=data.get("tmdb_id"),
                provider="manual",
            )
            item.confidence = Confidence.HIGH
            item.note = "set by hand"
            if item.is_tv and self.tmdb is not None and data.get("tmdb_id") and item.parsed.season is not None:
                titles = self.tmdb.season_episodes(data["tmdb_id"], item.parsed.season)
                found = titles.get(item.parsed.episode or -1, "")
                if found:
                    item.meta.episode_title = found


def _offline(item: Item) -> Confidence:
    if not item.parsed.title:
        return Confidence.NONE
    if item.is_tv:
        if item.parsed.season is not None and item.parsed.episode is not None:
            return Confidence.HIGH
        return Confidence.LOW
    return Confidence.HIGH if item.parsed.year else Confidence.LOW
