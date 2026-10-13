"""Problems a renamer cannot fix.

A correctly named library can still be missing the middle of a season, carry a
34 GB archive of episodes that are already extracted beside it, or hold a 720p
copy of something you also have at 1080p. None of that is a naming fault, so
none of it shows up in the plan. This pass looks for it.
"""
from __future__ import annotations

import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

from endslate import subtitles as subs_mod
from endslate.models import FileKind, Item, ScannedFile
from endslate.planner import _extracted_videos, collect_items
from endslate.scanner import LibraryScan

ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz", ".iso"}
ARCHIVE_MIN_BYTES = 200_000_000
TINY_VIDEO_BYTES = 20_000_000
RESOLUTION_ORDER = ["480p", "576p", "720p", "1080p", "1440p", "2160p", "4k"]

PROBLEM = "problem"
WARNING = "warning"
NOTE = "note"

SEVERITY_ORDER = {PROBLEM: 0, WARNING: 1, NOTE: 2}
SEVERITY_TONE = {PROBLEM: "red", WARNING: "amber", NOTE: "blue"}


@dataclass
class Finding:
    severity: str
    kind: str
    title: str
    detail: str
    paths: list[Path] = field(default_factory=list)
    bytes_involved: int = 0

    @property
    def tone(self) -> str:
        return SEVERITY_TONE.get(self.severity, "neutral")

    @property
    def primary(self) -> Optional[Path]:
        return self.paths[0] if self.paths else None


@dataclass
class HealthReport:
    findings: list[Finding] = field(default_factory=list)
    episodes_checked: int = 0
    videos_checked: int = 0

    def by_severity(self, severity: str) -> list[Finding]:
        return [f for f in self.findings if f.severity == severity]

    def counts(self) -> dict[str, int]:
        out = {PROBLEM: 0, WARNING: 0, NOTE: 0}
        for finding in self.findings:
            out[finding.severity] = out.get(finding.severity, 0) + 1
        return out

    @property
    def reclaimable(self) -> int:
        return sum(f.bytes_involved for f in self.findings if f.kind in ("redundant_archive", "lower_quality"))


def _human(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit in ("B", "KB") else f"{value:.1f} {unit}"
        value /= 1024.0
    return ""


# ------------------------------------------------------------------ the checks


def _missing_episodes(items: list[Item]) -> list[Finding]:
    seasons: dict[tuple[str, int], dict[int, Item]] = defaultdict(dict)
    for item in items:
        if not item.is_tv or item.parsed.season is None or item.parsed.episode is None:
            continue
        seasons[(item.show_hint or item.parsed.title, item.parsed.season)][item.parsed.episode] = item

    out: list[Finding] = []
    for (show, season), episodes in sorted(seasons.items()):
        numbers = sorted(episodes)
        if len(numbers) < 2:
            continue
        gaps = [n for n in range(numbers[0], numbers[-1] + 1) if n not in episodes]
        if not gaps:
            continue
        listed = ", ".join(f"E{n:02}" for n in gaps[:12])
        if len(gaps) > 12:
            listed += f" and {len(gaps) - 12} more"
        out.append(
            Finding(
                severity=PROBLEM if len(gaps) > 2 else WARNING,
                kind="missing_episodes",
                title=f"{show}, season {season}: {len(gaps)} episode{'s' if len(gaps) != 1 else ''} missing",
                detail=f"Present: E{numbers[0]:02} to E{numbers[-1]:02}. Missing: {listed}.",
                paths=[episodes[numbers[0]].video.path.parent],
            )
        )
    return out


def _redundant_archives(scan: LibraryScan) -> list[Finding]:
    out: list[Finding] = []
    for f in scan.files:
        if f.path.suffix.lower() not in ARCHIVE_EXTS or f.size < ARCHIVE_MIN_BYTES:
            continue
        # The planner's own test, so the two screens never disagree about an archive.
        siblings = _extracted_videos(f, scan)
        if siblings:
            in_downloads = scan.downloads_root is not None and _under(f.path, scan.downloads_root)
            fate = ("It goes to _Quarantine when the next run organises those videos."
                    if in_downloads else "Endslate will not touch it.")
            out.append(
                Finding(
                    severity=WARNING,
                    kind="redundant_archive",
                    title=f"{f.path.name} looks already extracted",
                    detail=(
                        f"{_human(f.size)} archive with {len(siblings)} video file"
                        f"{'s' if len(siblings) != 1 else ''} beside it. {fate}"
                    ),
                    paths=[f.path],
                    bytes_involved=f.size,
                )
            )
        else:
            out.append(
                Finding(
                    severity=NOTE,
                    kind="unextracted_archive",
                    title=f"{f.path.name} has not been extracted",
                    detail=f"{_human(f.size)} archive with no video beside it.",
                    paths=[f.path],
                )
            )
    return out


def _lower_quality_duplicates(items: list[Item]) -> list[Finding]:
    groups: dict[tuple[str, Optional[int]], list[Item]] = defaultdict(list)
    for item in items:
        if item.is_tv or not item.title:
            continue
        groups[(item.title.lower(), item.year)].append(item)

    out: list[Finding] = []
    for (_title, _year), group in sorted(groups.items()):
        if len(group) < 2:
            continue
        parts = {item.parsed.part for item in group}
        if len(parts) == len(group) and all(parts):
            continue  # different cuts, not duplicates
        ranked = sorted(group, key=lambda i: (_resolution_rank(i), i.video.size), reverse=True)
        best, rest = ranked[0], ranked[1:]
        wasted = sum(item.video.size for item in rest)
        out.append(
            Finding(
                severity=WARNING,
                kind="lower_quality",
                title=f"{best.title} ({best.year or 'no year'}) is here more than once",
                detail=(
                    f"Best copy: {best.parsed.resolution or 'unknown'} at {_human(best.video.size)}. "
                    f"{len(rest)} other cop{'ies' if len(rest) != 1 else 'y'} using {_human(wasted)}."
                ),
                paths=[item.video.path for item in ranked],
                bytes_involved=wasted,
            )
        )
    return out


def _resolution_rank(item: Item) -> int:
    resolution = (item.parsed.resolution or "").lower()
    return RESOLUTION_ORDER.index(resolution) if resolution in RESOLUTION_ORDER else -1


def _suspect_videos(scan: LibraryScan) -> list[Finding]:
    out: list[Finding] = []
    for f in scan.files:
        if f.kind is not FileKind.VIDEO:
            continue
        if f.size == 0:
            out.append(
                Finding(
                    severity=PROBLEM,
                    kind="empty_file",
                    title=f"{f.path.name} is empty",
                    detail="Zero bytes. A failed download or a broken copy.",
                    paths=[f.path],
                )
            )
        elif f.size < TINY_VIDEO_BYTES:
            out.append(
                Finding(
                    severity=WARNING,
                    kind="tiny_video",
                    title=f"{f.path.name} is only {_human(f.size)}",
                    detail="Too small for a film or an episode. Probably a sample or a broken file.",
                    paths=[f.path],
                )
            )
    return out


def _orphan_subtitles(scan: LibraryScan, items: list[Item]) -> list[Finding]:
    subs = [f for f in scan.files if f.kind is FileKind.SUBTITLE]
    _paired, orphans = subs_mod.pair(subs, items, scan.videos_under)
    if not orphans:
        return []
    listed = "\n".join(str(sub.path) for sub in orphans[:10])
    return [
        Finding(
            severity=NOTE,
            kind="orphan_subtitle",
            title=f"{len(orphans)} subtitle{'s' if len(orphans) != 1 else ''} match no video",
            detail=f"They will be left where they are.\n{listed}",
            paths=[sub.path for sub in orphans],
        )
    ]


def _empty_folders(scan: LibraryScan) -> list[Finding]:
    from endslate.scanner import empty_dirs

    empties = empty_dirs(scan)
    if not empties:
        return []
    return [
        Finding(
            severity=NOTE,
            kind="empty_folder",
            title=f"{len(empties)} empty folder{'s' if len(empties) != 1 else ''}",
            detail="\n".join(str(path) for path in empties[:10]),
            paths=empties,
        )
    ]


def _under(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


# --------------------------------------------------------------------- driver


def inspect(scan: LibraryScan, progress: Optional[Callable[[str, int, int], None]] = None) -> HealthReport:
    """Everything above, in one pass. Reads only."""
    if progress:
        progress("reading the library", 0, 0)
    items = collect_items(scan)
    report = HealthReport(
        episodes_checked=sum(1 for item in items if item.is_tv),
        videos_checked=len(items),
    )
    checks = (
        ("looking for missing episodes", lambda: _missing_episodes(items)),
        ("looking for redundant archives", lambda: _redundant_archives(scan)),
        ("looking for duplicate copies", lambda: _lower_quality_duplicates(items)),
        ("looking for broken files", lambda: _suspect_videos(scan)),
        ("looking for orphan subtitles", lambda: _orphan_subtitles(scan, items)),
        ("looking for empty folders", lambda: _empty_folders(scan)),
    )
    for index, (stage, check) in enumerate(checks):
        if progress:
            progress(stage, index, len(checks))
        report.findings.extend(check())

    report.findings.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), -f.bytes_involved, f.title))
    return report


# ------------------------------------------------------------- playability


def probe(paths: Iterable[Path], timeout: int = 20) -> list[Finding]:
    """Ask ffprobe whether a file actually opens. Only worth it on suspects."""
    out: list[Finding] = []
    for path in paths:
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=codec_name", "-of", "default=nw=1:nk=1",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            return [
                Finding(
                    severity=NOTE,
                    kind="no_ffprobe",
                    title="ffprobe is not installed",
                    detail="Install FFmpeg and put it on PATH to check whether files actually play.",
                )
            ]
        except Exception as exc:
            out.append(
                Finding(
                    severity=WARNING,
                    kind="unreadable",
                    title=f"{path.name} could not be probed",
                    detail=str(exc),
                    paths=[path],
                )
            )
            continue
        if result.returncode != 0 or not result.stdout.strip():
            out.append(
                Finding(
                    severity=PROBLEM,
                    kind="unplayable",
                    title=f"{path.name} has no readable video stream",
                    detail=(result.stderr or "ffprobe found no video stream.").strip()[:300],
                    paths=[path],
                )
            )
    return out
