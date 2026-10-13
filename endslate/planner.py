"""Turn a scan plus a preset into a plan. Nothing here touches the filesystem."""
from __future__ import annotations

import datetime as _dt
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from endslate import subtitles as subs_mod
from endslate.models import (
    Bucket,
    Confidence,
    FileKind,
    Item,
    Operation,
    OpKind,
    ParsedName,
    Plan,
    PlanEntry,
    ScannedFile,
)
from endslate.matcher import offline_confidence
from endslate.parser import SUBTITLE_EXTS as SUBTITLE_SUFFIXES, merge, parse
from endslate.presets import Preset, build_tokens, render
from endslate.sanitize import MAX_PATH, sanitize_component, shorten_to_fit
from endslate.scanner import QUARANTINE_DIRNAME, LibraryScan

BIG_ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz", ".iso"}
BIG_ARCHIVE_BYTES = 1_000_000_000


@dataclass
class Dirs:
    """Where each kind of item lands."""

    movies: Path
    shows: Path
    anime: Path

    def for_item(self, item: Item) -> Path:
        return {"movies": self.movies, "shows": self.shows, "anime": self.anime}[item.destination]


@dataclass
class Options:
    english_only_subtitles: bool = True
    quarantine_junk: bool = True
    rename_top_level_folders: bool = True
    folder_per_movie: Optional[bool] = None  # None means "follow the preset"
    subtitle_language: str = "en"
    run_stamp: str = field(default_factory=lambda: _dt.datetime.now().strftime("%Y-%m-%d_%H%M%S"))


def build_plan(
    scan: LibraryScan,
    preset: Preset,
    options: Optional[Options] = None,
    matcher: Optional[Callable[[list[Item]], None]] = None,
    progress: Optional[Callable[[str, int, int], None]] = None,
) -> Plan:
    options = options or Options()
    plan = Plan(root=scan.root, preset=preset.name)

    quarantine_root = scan.root / QUARANTINE_DIRNAME / options.run_stamp
    plan.quarantine_root = quarantine_root
    junk_dirs = _whole_junk_dirs(scan)

    items = _collect_items(scan, junk_dirs)
    if matcher is not None and items:
        matcher(items)
    else:
        for item in items:
            item.confidence = _offline_confidence(item)
            if item.is_tv and item.parsed.absolute is not None and not item.parsed.is_episode:
                item.note = ABSOLUTE_NOTE.format(n=item.parsed.absolute)

    sub_files = [
        f for f in scan.files
        if f.kind is FileKind.SUBTITLE and not _under_any(f.path, junk_dirs)
    ]
    paired, orphan_subs = subs_mod.pair(sub_files, items, scan.videos_under)
    for sub_path, item in paired.items():
        item.subtitles.append(_file_for(scan, sub_path))

    rename = options.rename_top_level_folders
    dirs = Dirs(
        movies=scan.root / (preset.movies_dir if rename else _existing_name(scan.movies_root, preset.movies_dir)),
        shows=scan.root / (preset.shows_dir if rename else _existing_name(scan.shows_root, preset.shows_dir)),
        anime=scan.root / (preset.anime_dir if rename else _existing_name(scan.anime_root, preset.anime_dir)),
    )

    folder_per_movie = preset.folder_per_movie if options.folder_per_movie is None else options.folder_per_movie

    targets: dict[Path, list[PlanEntry]] = defaultdict(list)
    total = len(items)
    for index, item in enumerate(items):
        if progress is not None and index % 25 == 0:
            progress("planning", index, total)
        entry = _entry_for(item, preset, options, dirs, folder_per_movie)
        plan.entries.append(entry)
        if entry.bucket is Bucket.PLANNED:
            target = entry.target_path
            if target is not None:
                targets[target].append(entry)

    _resolve_collisions(plan, targets, preset, options, dirs, folder_per_movie)

    if options.quarantine_junk:
        plan.entries.extend(_junk_entries(scan, junk_dirs, quarantine_root))
        if options.english_only_subtitles:
            kept = {op.src for entry in plan.entries for op in entry.ops
                    if op.kind is OpKind.MOVE and op.src is not None and op.src.suffix.lower() in SUBTITLE_SUFFIXES}
            # Only a subtitle that lost to a better track of the same language
            # is redundant. One that is already in place, or belongs to a file
            # still waiting on you, stays where it is.
            redundant = {path for entry in plan.entries
                         if entry.bucket in (Bucket.PLANNED, Bucket.NOOP)
                         for path in entry.dropped_subtitles}
            plan.entries.extend(_foreign_subtitle_entries(items, options, quarantine_root, scan.root,
                                                          kept, redundant))

    for sub in orphan_subs:
        if scan.downloads_root is not None and _under_any(sub.path, [scan.downloads_root]):
            continue
        plan.entries.append(
            PlanEntry(item=None, bucket=Bucket.SKIPPED, ops=[Operation(OpKind.MOVE, sub.path, None)],
                      reason="subtitle matched no video", selected=False)
        )

    for note in _notes(scan):
        plan.notes.append(note)
    if scan.errors:
        plan.notes.append(f"{len(scan.errors)} paths could not be read")
    return plan


# --------------------------------------------------------------------------- items


def _existing_name(path: Optional[Path], fallback: str) -> str:
    return path.name if path is not None else fallback


def _file_for(scan: LibraryScan, path: Path) -> ScannedFile:
    for f in scan.files:
        if f.path == path:
            return f
    return ScannedFile(path=path, size=0, kind=FileKind.SUBTITLE)


def _under_any(path: Path, directories: list[Path]) -> bool:
    for directory in directories:
        try:
            path.relative_to(directory)
            return True
        except ValueError:
            continue
    return False


def _whole_junk_dirs(scan: LibraryScan) -> list[Path]:
    """Top-level folders holding no video and no subtitle anywhere beneath."""
    out: list[Path] = []
    for root in (scan.movies_root, scan.shows_root, scan.anime_root):
        if root is None:
            continue
        for child in scan.subdirs(root):
            has_media = any(
                f.kind in (FileKind.VIDEO, FileKind.SUBTITLE) and _under_any(f.path, [child])
                for f in scan.files
            )
            if not has_media:
                out.append(child)
    return out


def _ancestor_parses(path: Path, stop_at: Optional[Path], anime: bool = False) -> list[ParsedName]:
    out: list[ParsedName] = []
    current = path.parent
    while stop_at is not None and current != stop_at and current != current.parent:
        out.append(parse(current.name, is_dir=True, anime=anime))
        current = current.parent
    return out


def _root_of(path: Path, scan: LibraryScan) -> tuple[str, Optional[Path]]:
    """Which top-level folder a file sits in, and that folder."""
    for name, root in (
        ("anime", scan.anime_root),
        ("shows", scan.shows_root),
        ("downloads", scan.downloads_root),
        ("movies", scan.movies_root),
    ):
        if root is not None and _under_any(path, [root]):
            return name, root
    return "", scan.movies_root


def _collect_items(scan: LibraryScan, junk_dirs: list[Path]) -> list[Item]:
    items: list[Item] = []
    for f in scan.files:
        if f.kind is not FileKind.VIDEO or _under_any(f.path, junk_dirs):
            continue
        where, stop = _root_of(f.path, scan)
        in_anime = where == "anime"
        parsed = parse(f.path.name, anime=in_anime)
        for ancestor in _ancestor_parses(f.path, stop, anime=in_anime):
            parsed = merge(parsed, ancestor)

        # Where a file sits decides what it is. Shows holds episodes. Anime
        # holds episodes and the odd film, which belongs with the films.
        # Downloads holds anything, so the name decides: a fansub release is
        # anime, an episode marker is a show, everything else is a film.
        is_anime = False
        if where == "shows":
            is_tv = True
            # A fansub file numbered from the start of the show cannot be
            # placed in a season without TheTVDB. Anything else stays on TMDB.
            is_anime = parsed.absolute is not None and not parsed.is_episode
            section = "shows"
        elif where == "anime":
            is_tv = parsed.has_episode_number or parsed.season is not None
            is_anime = is_tv
            section = "anime" if is_tv else "movies"
        elif where == "downloads":
            is_tv = parsed.has_episode_number
            is_anime = is_tv and (parsed.anime_hint or not parsed.is_episode)
            section = ("anime" if is_tv and parsed.anime_hint else "shows") if is_tv else "movies"
        else:
            is_tv = False
            section = "movies"

        show_hint = ""
        if is_tv and stop is not None:
            relative = f.path.relative_to(stop)
            if len(relative.parts) > 1:
                show_hint = relative.parts[0]
                show_parse = parse(show_hint, is_dir=True, anime=in_anime)
                if show_parse.title:
                    parsed.title = show_parse.title
                if parsed.year is None and show_parse.year:
                    parsed.year = show_parse.year
                if parsed.tvdb_id is None:
                    parsed.tvdb_id = show_parse.tvdb_id
            else:
                show_hint = parsed.title
        items.append(Item(video=f, is_tv=is_tv, is_anime=is_anime, section=section,
                          show_hint=show_hint or parsed.title, parsed=parsed))
    return items


def collect_items(scan: LibraryScan) -> list[Item]:
    """Every video in the library, parsed. Used by the health pass as well."""
    return _collect_items(scan, _whole_junk_dirs(scan))


_offline_confidence = offline_confidence


# --------------------------------------------------------------------------- targets


ABSOLUTE_NOTE = (
    "episode {n} is counted from the start of the show; TheTVDB is needed to "
    "place it in a season"
)


def _entry_for(
    item: Item,
    preset: Preset,
    options: Options,
    dirs: Dirs,
    folder_per_movie: bool,
    disambiguator: str = "",
) -> PlanEntry:
    if item.confidence in (Confidence.LOW, Confidence.NONE):
        bucket = Bucket.NEEDS_YOU if item.parsed.title else Bucket.SKIPPED
        reason = item.note or ("no year and no confident match" if item.parsed.title else "nothing parseable in the name")
        return PlanEntry(item=item, bucket=bucket, reason=reason, selected=False)

    if item.is_tv and (item.parsed.season is None or item.parsed.episode is None):
        reason = "no season or episode number"
        if item.parsed.absolute is not None:
            reason = item.note or ABSOLUTE_NOTE.format(n=item.parsed.absolute)
        return PlanEntry(item=item, bucket=Bucket.NEEDS_YOU, reason=reason, selected=False)

    tokens = build_tokens(
        title=item.title,
        year=item.year,
        season=item.parsed.season,
        episode=item.parsed.episode,
        episode_end=item.parsed.episode_end,
        absolute=item.parsed.absolute,
        episode_title=item.episode_title,
        edition=item.parsed.edition,
        part=item.parsed.part,
        resolution=item.parsed.resolution,
        source=item.parsed.source,
        tmdb_id=item.meta.tmdb_id,
        imdb_id=item.meta.imdb_id,
        tvdb_id=item.meta.tvdb_id or item.parsed.tvdb_id,
        ext=item.video.path.suffix.lstrip("."),
    )

    root = dirs.for_item(item)
    if item.is_tv:
        template = preset.anime_folder if item.destination == "anime" else preset.movie_folder
        show_folder = sanitize_component(render(template, tokens))
        season_folder = sanitize_component(render(preset.season_folder, tokens))
        directory = root / show_folder / season_folder
        stem = sanitize_component(render(preset.episode_file, tokens))
    else:
        stem = sanitize_component(render(preset.movie_file, tokens))
        if folder_per_movie:
            directory = root / sanitize_component(render(preset.movie_folder, tokens))
        else:
            directory = root

    if disambiguator:
        stem = sanitize_component(f"{stem} - {disambiguator}")
    suffix = item.video.path.suffix.lower()
    stem = shorten_to_fit(str(directory), stem, suffix)
    target = directory / (stem + suffix)

    ops: list[Operation] = []
    if target != item.video.path:
        ops.append(Operation(OpKind.MKDIR, None, directory, reason="destination folder"))
        ops.append(Operation(OpKind.MOVE, item.video.path, target, size=item.video.size, reason="video"))

    dropped: list[Path] = []
    for sub, code, sub_target in _subtitle_targets(item, options, directory, stem):
        if sub_target is None:
            dropped.append(sub.path)
            continue
        if sub_target != sub.path:
            ops.append(Operation(OpKind.MOVE, sub.path, sub_target, size=sub.size, reason=f"subtitle ({code})"))

    if not ops:
        return PlanEntry(item=item, bucket=Bucket.NOOP, reason="already correctly named", selected=False,
                         dropped_subtitles=dropped)

    entry = PlanEntry(item=item, bucket=Bucket.PLANNED, ops=ops, dropped_subtitles=dropped)
    if len(str(target)) >= MAX_PATH:
        entry.bucket = Bucket.NEEDS_YOU
        entry.selected = False
        entry.reason = f"target path is {len(str(target))} characters"
    elif item.confidence is Confidence.MEDIUM:
        entry.reason = item.note or "fuzzy title match"
    return entry


def _disambiguators(items: list[Item]) -> Optional[list[str]]:
    """Find a field that tells colliding items apart, e.g. Remastered vs Theatrical."""
    for field_name in ("edition", "part", "resolution", "source"):
        values = [getattr(item.parsed, field_name, "") or "" for item in items]
        if all(values) and len(set(values)) == len(values):
            return values
    return None


def _resolve_collisions(plan, targets, preset, options, dirs, folder_per_movie) -> None:
    """Two files wanting one name are either different cuts or a real duplicate."""
    for target, entries in list(targets.items()):
        if len(entries) < 2:
            continue
        items = [e.item for e in entries if e.item is not None]
        labels = _disambiguators(items) if len(items) == len(entries) else None
        if labels:
            for entry, label in zip(entries, labels):
                rebuilt = _entry_for(entry.item, preset, options, dirs,
                                     folder_per_movie, disambiguator=label)
                entry.ops = rebuilt.ops
                entry.bucket = rebuilt.bucket
                entry.dropped_subtitles = rebuilt.dropped_subtitles
                entry.reason = f"same name as another file, kept apart by {label}"
            continue
        for entry in entries:
            entry.bucket = Bucket.DUPLICATE
            entry.selected = False
            entry.reason = f"{len(entries)} files resolve to {target.name}"


# --------------------------------------------------------------------------- junk


def _subtitle_targets(item: Item, options: Options, directory: Path, stem: str):
    """Decide each subtitle's destination, keeping one track per language and flag set.

    A folder can hold three English subtitles (the sidecar, Subs/English.srt and
    Subs/British.eng.srt). They would all render to the same name, so the best one
    wins and the rest fall through to the quarantine pass.
    """
    chosen: dict[Path, tuple] = {}
    results: list[tuple] = []
    for sub in item.subtitles:
        language = subs_mod.detect_language(sub)
        if options.english_only_subtitles and language and language != options.subtitle_language:
            results.append((sub, language, None))
            continue
        code = language or options.subtitle_language
        target = directory / subs_mod.target_name(stem, sub, code)
        rank = (sub.path.parent == item.video.path.parent, sub.size)
        current = chosen.get(target)
        if current is None or rank > current[0]:
            if current is not None:
                results.append((current[1], current[2], None))
            chosen[target] = (rank, sub, code)
        else:
            results.append((sub, code, None))
    for target, (_rank, sub, code) in chosen.items():
        results.append((sub, code, target))
    return results


def _quarantine_target(path: Path, root: Path, quarantine_root: Path) -> Path:
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = Path(path.name)
    return quarantine_root / relative


def _junk_entries(scan: LibraryScan, junk_dirs: list[Path], quarantine_root: Path) -> list[PlanEntry]:
    out: list[PlanEntry] = []
    for directory in junk_dirs:
        target = _quarantine_target(directory, scan.root, quarantine_root)
        size = sum(f.size for f in scan.files if _under_any(f.path, [directory]))
        out.append(
            PlanEntry(
                item=None,
                bucket=Bucket.JUNK,
                ops=[Operation(OpKind.QUARANTINE, directory, target, size=size, reason="folder holds no media")],
                reason="folder holds no media",
            )
        )
    # Downloads is a staging area. Once an archive has been extracted beside
    # its videos, keep the organized videos and quarantine the bulky source
    # archive. An archive with no extracted video remains available for later.
    if scan.downloads_root is not None:
        for archive in scan.files:
            if archive.path.suffix.lower() not in BIG_ARCHIVE_EXTS:
                continue
            if not _in_downloads(archive.path, scan) or not _extracted_videos(archive, scan):
                continue
            target = _quarantine_target(archive.path, scan.root, quarantine_root)
            out.append(
                PlanEntry(
                    item=None,
                    bucket=Bucket.JUNK,
                    ops=[Operation(OpKind.QUARANTINE, archive.path, target,
                                   size=archive.size, reason="archive has extracted video files")],
                    reason="archive has extracted video files",
                )
            )
    for f in scan.files:
        if (f.kind is not FileKind.JUNK or _under_any(f.path, junk_dirs)
                or (scan.downloads_root is not None and _under_any(f.path, [scan.downloads_root]))):
            continue
        target = _quarantine_target(f.path, scan.root, quarantine_root)
        out.append(
            PlanEntry(
                item=None,
                bucket=Bucket.JUNK,
                ops=[Operation(OpKind.QUARANTINE, f.path, target, size=f.size, reason=f.junk_reason)],
                reason=f.junk_reason,
            )
        )
    return out


def _foreign_subtitle_entries(items: list[Item], options: Options, quarantine_root: Path, root: Path,
                              kept: set, redundant: set) -> list[PlanEntry]:
    """Subtitles in another language, and English ones a better track replaced.

    Every correctly named subtitle used to land here: one that was already in
    place had no move, so nothing marked it as kept, and Endslate proposed
    sweeping the only subtitle a film had into _Quarantine.
    """
    out: list[PlanEntry] = []
    for item in items:
        for sub in item.subtitles:
            if sub.path in kept:
                continue
            language = subs_mod.detect_language(sub)
            foreign = bool(language) and language != options.subtitle_language
            if not foreign and sub.path not in redundant:
                continue
            target = _quarantine_target(sub.path, root, quarantine_root)
            out.append(
                PlanEntry(
                    item=None,
                    bucket=Bucket.JUNK,
                    ops=[Operation(OpKind.QUARANTINE, sub.path, target, size=sub.size,
                                   reason=f"{language or 'duplicate English'} subtitle")],
                    reason=(f"{language} subtitle, English-only is on" if foreign
                            else "redundant subtitle, another track already covers this language"),
                )
            )
    return out


def duplicate_group(plan: Plan, entry: PlanEntry) -> list[PlanEntry]:
    """The other files fighting for the same name."""
    target = entry.target_path
    if target is None:
        return [entry]
    return [
        other for other in plan.entries
        if other.bucket is Bucket.DUPLICATE and other.target_path == target
    ]


def keep_one_of_duplicates(plan: Plan, keeper: PlanEntry) -> int:
    """Keep this copy, send the others to _Quarantine.

    Nothing is deleted here either. The losing copies move out of the library so
    the media server stops seeing them, and sit in _Quarantine until emptied.
    """
    group = duplicate_group(plan, keeper)
    if len(group) < 2:
        return 0
    target = keeper.target_path
    quarantine_root = plan.quarantine_root or (plan.root / QUARANTINE_DIRNAME / "manual")
    moved = 0
    for entry in group:
        if entry is keeper:
            entry.bucket = Bucket.PLANNED
            entry.selected = True
            entry.reason = "the copy you chose to keep"
            continue
        source = entry.source_path
        if source is None:
            continue
        size = entry.item.video.size if entry.item is not None else 0
        entry.bucket = Bucket.JUNK
        entry.selected = True
        entry.reason = f"duplicate of {target.name if target else 'the kept copy'}, not the one you kept"
        entry.ops = [
            Operation(
                OpKind.QUARANTINE,
                source,
                _quarantine_target(source, plan.root, quarantine_root),
                size=size,
                reason="duplicate you did not keep",
            )
        ]
        if entry.item is not None:
            for sub in entry.item.subtitles:
                entry.ops.append(
                    Operation(
                        OpKind.QUARANTINE,
                        sub.path,
                        _quarantine_target(sub.path, plan.root, quarantine_root),
                        size=sub.size,
                        reason="subtitle of a duplicate",
                    )
                )
        moved += 1
    return moved


def keep_largest_duplicates(plan: Plan) -> int:
    """Resolve every duplicate group at once, keeping the biggest file in each."""
    resolved = 0
    while True:
        remaining = [e for e in plan.entries if e.bucket is Bucket.DUPLICATE]
        if not remaining:
            break
        group = duplicate_group(plan, remaining[0])
        if len(group) < 2:
            remaining[0].bucket = Bucket.PLANNED
            remaining[0].selected = True
            continue
        keeper = max(group, key=lambda e: e.item.video.size if e.item is not None else 0)
        resolved += keep_one_of_duplicates(plan, keeper)
    return resolved


def _in_downloads(path: Path, scan: LibraryScan) -> bool:
    return scan.downloads_root is not None and _under_any(path, [scan.downloads_root])


def _extracted_videos(archive: ScannedFile, scan: LibraryScan) -> list[ScannedFile]:
    """The videos that came out of this archive, as far as the names can tell.

    An archive in its own folder owns every video in that folder. One lying
    loose in Downloads owns only the videos with its title: before this, any
    video anywhere in Downloads sent every loose archive to quarantine, and an
    archive outside Downloads was swept up the moment a Downloads folder existed.
    """
    videos = [
        v for v in scan.files
        if v.kind is FileKind.VIDEO and _under_any(v.path, [archive.path.parent])
    ]
    if archive.path.parent != scan.downloads_root:
        return videos
    from endslate.matcher import normalize_title

    wanted = normalize_title(parse(archive.path.name).title)
    if not wanted:
        return []
    return [v for v in videos if normalize_title(parse(v.path.name).title) == wanted]


def _notes(scan: LibraryScan) -> list[str]:
    notes: list[str] = []
    for f in scan.files:
        if f.path.suffix.lower() in BIG_ARCHIVE_EXTS and f.size >= BIG_ARCHIVE_BYTES:
            siblings = _extracted_videos(f, scan)
            gb = f.size / 1_000_000_000
            if siblings:
                in_downloads = _in_downloads(f.path, scan)
                action = "will be moved to _Quarantine after the extracted media is organized" if in_downloads else "left untouched"
                notes.append(
                    f"{f.path.name} is {gb:.1f} GB and {len(siblings)} video files sit beside it, "
                    f"so the archive looks already extracted; {action}."
                )
            else:
                notes.append(f"{f.path.name} is {gb:.1f} GB and nothing beside it is extracted. Left untouched.")
    return notes
