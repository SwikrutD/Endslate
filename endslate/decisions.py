"""What you have already told Endslate, kept between runs.

Resolving a title by hand used to live in memory and die with the window, so the
same five films came back every scan. A decision is stored twice: against the
file it was made on, which is exact but goes stale the moment the file is
renamed, and against the title it was made for, which survives renaming and
generalises to any other copy of the same thing.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from endslate.config import app_dir
from endslate.matcher import normalize_title

VERSION = 1


@dataclass
class Decision:
    title: str
    year: Optional[int] = None
    tmdb_id: Optional[int] = None
    tvdb_id: Optional[int] = None
    is_tv: bool = False
    source: str = ""
    decided_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))

    def to_meta(self) -> dict:
        return {"title": self.title, "year": self.year, "tmdb_id": self.tmdb_id, "tvdb_id": self.tvdb_id}


def title_key(title: str, is_tv: bool = False) -> str:
    kind = "tv" if is_tv else "movie"
    return f"{kind}:{normalize_title(title)}"


def store_path() -> Path:
    return app_dir() / "decisions.json"


class Decisions:
    """A small JSON file. Loaded once, written on every change."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or store_path()
        self.by_path: dict[str, Decision] = {}
        self.by_title: dict[str, Decision] = {}
        self.load()

    # ------------------------------------------------------------------- io

    def load(self) -> None:
        self.by_path, self.by_title = {}, {}
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if data.get("version") != VERSION:
            return
        known = set(Decision.__dataclass_fields__)
        for bucket, target in (("by_path", self.by_path), ("by_title", self.by_title)):
            for key, row in (data.get(bucket) or {}).items():
                try:
                    target[key] = Decision(**{k: v for k, v in row.items() if k in known})
                except TypeError:
                    continue

    def save(self) -> bool:
        payload = {
            "version": VERSION,
            "by_path": {k: asdict(v) for k, v in self.by_path.items()},
            "by_title": {k: asdict(v) for k, v in self.by_title.items()},
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            return True
        except OSError:
            return False

    # ---------------------------------------------------------------- write

    def remember(self, item, meta: dict) -> Decision:
        """Record a resolution, against this file and against its parsed title."""
        decision = Decision(
            title=meta.get("title", ""),
            year=meta.get("year"),
            tmdb_id=meta.get("tmdb_id"),
            tvdb_id=meta.get("tvdb_id"),
            is_tv=bool(item.is_tv),
            source=str(item.video.path),
        )
        self.by_path[str(item.video.path)] = decision
        guess = item.show_hint if item.is_tv else item.parsed.title
        if guess:
            self.by_title[title_key(guess, item.is_tv)] = decision
        return decision

    def forget_all(self) -> int:
        count = len(self.by_path) + len(self.by_title)
        self.by_path, self.by_title = {}, {}
        self.save()
        return count

    def forget(self, item) -> bool:
        removed = self.by_path.pop(str(item.video.path), None) is not None
        guess = item.show_hint if item.is_tv else item.parsed.title
        if guess:
            removed = self.by_title.pop(title_key(guess, item.is_tv), None) is not None or removed
        if removed:
            self.save()
        return removed

    # ----------------------------------------------------------------- read

    def lookup(self, item) -> Optional[Decision]:
        found = self.by_path.get(str(item.video.path))
        if found is not None:
            return found
        guess = item.show_hint if item.is_tv else item.parsed.title
        if not guess:
            return None
        return self.by_title.get(title_key(guess, item.is_tv))

    def __len__(self) -> int:
        return len(self.by_title)

    @property
    def titles(self) -> list[Decision]:
        return sorted(self.by_title.values(), key=lambda d: d.title.lower())
