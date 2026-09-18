"""Pair subtitle files to the video they belong to."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from endslate.langs import normalize as norm_lang
from endslate.models import FileKind, Item, ScannedFile
from endslate.parser import parse

SUBS_DIRNAMES = {"subs", "subtitles", "subtitle", "sub"}
_FLAG_RE = re.compile(r"(?<![A-Za-z0-9])(forced|sdh|cc|hi)(?![A-Za-z0-9])", re.I)


def detect_flags(name: str) -> list[str]:
    seen = []
    for match in _FLAG_RE.finditer(name):
        flag = match.group(1).lower()
        flag = "sdh" if flag in ("sdh", "cc", "hi") else flag
        if flag not in seen:
            seen.append(flag)
    return seen


def detect_language(sub: ScannedFile) -> str:
    """Language for one subtitle, using its name then its folder name."""
    code = parse(sub.path.name).language
    if code:
        return code
    whole = norm_lang(sub.path.stem)
    if whole:
        return whole
    folder = norm_lang(sub.path.parent.name)
    if folder:
        return folder
    # "Dark - season 1.en" style: the code is the folder's extension.
    suffix = sub.path.parent.suffix.lstrip(".")
    if suffix:
        code = norm_lang(suffix)
        if code:
            return code
    return ""


def _normalized_stem(name: str) -> str:
    parsed = parse(name)
    base = parsed.title.lower()
    return re.sub(r"[^a-z0-9]+", "", base)


def pair(
    subs: list[ScannedFile],
    items: list[Item],
    videos_under,
) -> tuple[dict[Path, Item], list[ScannedFile]]:
    """Return (subtitle path -> item) and the subtitles nothing claimed."""
    by_dir: dict[Path, list[Item]] = {}
    by_episode: dict[tuple[str, int, int], Item] = {}
    for item in items:
        by_dir.setdefault(item.video.path.parent, []).append(item)
        if item.is_tv and item.parsed.season is not None and item.parsed.episode is not None:
            key = (item.show_hint.lower(), item.parsed.season, item.parsed.episode)
            by_episode.setdefault(key, item)

    paired: dict[Path, Item] = {}
    orphans: list[ScannedFile] = []

    for sub in subs:
        item = _find_owner(sub, by_dir, by_episode, items, videos_under)
        if item is None:
            orphans.append(sub)
        else:
            paired[sub.path] = item
    return paired, orphans


def _show_hint_for(path: Path, items: list[Item]) -> str:
    best = ""
    best_len = -1
    for item in items:
        if not item.is_tv:
            continue
        try:
            common = len(set(path.parents) & set(item.video.path.parents))
        except TypeError:
            common = 0
        if common > best_len:
            best_len = common
            best = item.show_hint
    return best


def _find_owner(
    sub: ScannedFile,
    by_dir: dict[Path, list[Item]],
    by_episode: dict[tuple[str, int, int], Item],
    items: list[Item],
    videos_under,
) -> Optional[Item]:
    here = by_dir.get(sub.path.parent, [])
    if len(here) == 1:
        return here[0]

    parsed = parse(sub.path.name)
    if parsed.season is not None and parsed.episode is not None:
        hint = _show_hint_for(sub.path, items)
        found = by_episode.get((hint.lower(), parsed.season, parsed.episode))
        if found is not None:
            return found
        # Fall back to any show with that episode, when only one matches.
        matches = [
            item for key, item in by_episode.items()
            if key[1] == parsed.season and key[2] == parsed.episode
            and _shares_ancestor(sub.path, item.video.path)
        ]
        if len(matches) == 1:
            return matches[0]

    if here:
        target = _normalized_stem(sub.path.stem)
        for item in here:
            if _normalized_stem(item.video.path.stem) == target:
                return item

    # A Subs folder, or any ancestor holding exactly one video.
    directory = sub.path.parent
    while True:
        videos = videos_under(directory)
        if len(videos) == 1:
            for item in items:
                if item.video.path == videos[0].path:
                    return item
        if directory.parent == directory or len(directory.parts) <= 2:
            return None
        if not _worth_climbing(directory, sub):
            return None
        directory = directory.parent


def _worth_climbing(directory: Path, sub: ScannedFile) -> bool:
    # Only climb out of a subtitle-ish folder or the folder the subtitle sits in.
    return directory == sub.path.parent or directory.name.lower() in SUBS_DIRNAMES or directory.suffix.lstrip(".").isalpha()


def _shares_ancestor(a: Path, b: Path, depth: int = 3) -> bool:
    return len(set(a.parents) & set(b.parents)) >= depth


def target_name(video_stem: str, sub: ScannedFile, language: str) -> str:
    """Jellyfin external-subtitle name: <video stem>.<lang>[.forced|.sdh]<ext>."""
    parts = [video_stem]
    if language:
        parts.append(language)
    for flag in detect_flags(sub.path.name):
        parts.append(flag)
    return ".".join(parts) + sub.path.suffix.lower()
