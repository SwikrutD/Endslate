"""Read the library. This module never writes."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from endslate import fsops, junk
from endslate.models import FileKind, ScannedFile

QUARANTINE_DIRNAME = "_Quarantine"
DOWNLOADS_DIRNAME = "Downloads"

MOVIE_DIR_NAMES = ("movies", "movie", "films", "film")
SHOW_DIR_NAMES = ("tv shows", "tvshows", "shows", "series", "tv")
ANIME_DIR_NAMES = ("anime", "anime shows", "anime series")


@dataclass
class LibraryScan:
    root: Path
    files: list[ScannedFile] = field(default_factory=list)
    dirs: list[Path] = field(default_factory=list)
    children: dict[Path, list[Path]] = field(default_factory=dict)
    movies_root: Optional[Path] = None
    shows_root: Optional[Path] = None
    anime_root: Optional[Path] = None
    downloads_root: Optional[Path] = None
    errors: list[str] = field(default_factory=list)

    def files_in(self, directory: Path) -> list[ScannedFile]:
        return [f for f in self.files if f.path.parent == directory]

    def subdirs(self, directory: Path) -> list[Path]:
        return [p for p in self.children.get(directory, []) if p.is_dir()]

    def videos_under(self, directory: Path) -> list[ScannedFile]:
        return [
            f for f in self.files
            if f.kind is FileKind.VIDEO and _is_under(f.path, directory)
        ]

    @property
    def total_bytes(self) -> int:
        return sum(f.size for f in self.files)


def _is_under(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def _match_root(root: Path, names: Iterable[str]) -> Optional[Path]:
    try:
        entries = [root / name for name in fsops.listdir(root)]
        entries = [p for p in entries if fsops.is_dir(p)]
    except OSError:
        return None
    for entry in entries:
        if entry.name.lower() in names:
            return entry
    return None


def scan(root: Path) -> LibraryScan:
    """Walk the library once, classifying every file."""
    root = Path(root)
    result = LibraryScan(root=root)

    for here, dirnames, filenames in fsops.walk_with_errors(root, result.errors.append):
        if QUARANTINE_DIRNAME in here.parts:
            dirnames[:] = []
            continue
        dirnames[:] = sorted(d for d in dirnames if d != QUARANTINE_DIRNAME)
        filenames.sort()

        result.children[here] = [here / d for d in dirnames] + [here / f for f in filenames]
        if here != root:
            result.dirs.append(here)

        for filename in filenames:
            path = here / filename
            try:
                size = fsops.size(path)
            except OSError as exc:
                result.errors.append(f"{path}: {exc}")
                size = 0
            kind_name, reason = junk.classify(path, size)
            result.files.append(
                ScannedFile(path=path, size=size, kind=FileKind(kind_name), junk_reason=reason)
            )

    result.movies_root = _match_root(root, MOVIE_DIR_NAMES)
    result.shows_root = _match_root(root, SHOW_DIR_NAMES)
    result.anime_root = _match_root(root, ANIME_DIR_NAMES)
    result.downloads_root = _match_root(root, (DOWNLOADS_DIRNAME.lower(),))
    return result


def empty_dirs(scan_result: LibraryScan) -> list[Path]:
    """Directories with no files anywhere beneath them."""
    out = []
    for directory in scan_result.dirs:
        if not any(_is_under(f.path, directory) for f in scan_result.files):
            out.append(directory)
    return sorted(out, key=lambda p: len(p.parts), reverse=True)
