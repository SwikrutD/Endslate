"""Core data types. Nothing here touches the filesystem."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class FileKind(str, Enum):
    VIDEO = "video"
    SUBTITLE = "subtitle"
    ARTWORK = "artwork"
    JUNK = "junk"
    OTHER = "other"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class OpKind(str, Enum):
    MKDIR = "mkdir"
    MOVE = "move"
    QUARANTINE = "quarantine"
    RMDIR = "rmdir"


class Bucket(str, Enum):
    PLANNED = "planned"
    NEEDS_YOU = "needs_you"
    DUPLICATE = "duplicate"
    JUNK = "junk"
    SKIPPED = "skipped"
    NOOP = "noop"


@dataclass
class ScannedFile:
    path: Path
    size: int
    kind: FileKind
    junk_reason: str = ""

    @property
    def ext(self) -> str:
        return self.path.suffix.lower()

    @property
    def stem(self) -> str:
        return self.path.stem


@dataclass
class ParsedName:
    """What the filename alone claims. Best-effort, never authoritative."""

    title: str = ""
    year: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    episode_end: Optional[int] = None
    episode_title: str = ""
    edition: str = ""
    part: str = ""
    language: str = ""
    resolution: str = ""
    source: str = ""
    is_sample: bool = False

    @property
    def is_episode(self) -> bool:
        return self.season is not None and self.episode is not None


@dataclass
class Metadata:
    """What the provider says. Authoritative when present."""

    title: str = ""
    year: Optional[int] = None
    episode_title: str = ""
    tmdb_id: Optional[int] = None
    imdb_id: str = ""
    provider: str = ""


@dataclass
class Candidate:
    title: str
    year: Optional[int]
    tmdb_id: int
    overview: str = ""
    score: float = 0.0

    @property
    def label(self) -> str:
        return f"{self.title} ({self.year})" if self.year else self.title


@dataclass
class Item:
    """One video plus the subtitles that belong to it."""

    video: ScannedFile
    subtitles: list[ScannedFile] = field(default_factory=list)
    artwork: list[ScannedFile] = field(default_factory=list)
    is_tv: bool = False
    show_hint: str = ""
    parsed: ParsedName = field(default_factory=ParsedName)
    meta: Metadata = field(default_factory=Metadata)
    confidence: Confidence = Confidence.NONE
    candidates: list[Candidate] = field(default_factory=list)
    note: str = ""

    @property
    def title(self) -> str:
        return self.meta.title or self.parsed.title

    @property
    def year(self) -> Optional[int]:
        return self.meta.year if self.meta.year is not None else self.parsed.year

    @property
    def episode_title(self) -> str:
        return self.meta.episode_title or self.parsed.episode_title

    @property
    def key(self) -> str:
        if self.is_tv:
            return f"tv:{self.title.lower()}:{self.parsed.season}:{self.parsed.episode}"
        return f"movie:{self.title.lower()}:{self.year}"


@dataclass
class Operation:
    kind: OpKind
    src: Optional[Path]
    dst: Optional[Path]
    size: int = 0
    reason: str = ""


@dataclass
class PlanEntry:
    """One reviewable row: an item and the operations it implies."""

    item: Optional[Item]
    bucket: Bucket
    ops: list[Operation] = field(default_factory=list)
    reason: str = ""
    selected: bool = True

    @property
    def source_path(self) -> Optional[Path]:
        if self.item is not None:
            return self.item.video.path
        return self.ops[0].src if self.ops else None

    @property
    def target_path(self) -> Optional[Path]:
        for op in self.ops:
            if op.kind in (OpKind.MOVE, OpKind.QUARANTINE):
                return op.dst
        return None


@dataclass
class Plan:
    root: Path
    preset: str
    entries: list[PlanEntry] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def by_bucket(self, bucket: Bucket) -> list[PlanEntry]:
        return [e for e in self.entries if e.bucket == bucket]

    def selected_operations(self) -> list[Operation]:
        ops: list[Operation] = []
        for entry in self.entries:
            if entry.selected and entry.bucket in (Bucket.PLANNED, Bucket.JUNK):
                ops.extend(entry.ops)
        return ops

    def counts(self) -> dict[str, int]:
        out = {b.value: 0 for b in Bucket}
        for entry in self.entries:
            out[entry.bucket.value] += 1
        return out
