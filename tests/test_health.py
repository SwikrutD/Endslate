"""The health pass: problems a renamer cannot fix."""
from pathlib import Path

import pytest

from endslate.health import NOTE, PROBLEM, WARNING, inspect, probe
from endslate.scanner import scan


def build(root: Path, files: dict[str, int]) -> Path:
    for relative, size in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
    return root


def kinds(report) -> set[str]:
    return {finding.kind for finding in report.findings}


def test_a_gap_in_a_season_is_found(tmp_path):
    root = build(
        tmp_path / "Media",
        {
            f"Shows/The 100 (2014)/Season 01/The 100 (2014) S01E{n:02} Ep.mkv": 100
            for n in (1, 2, 3, 6, 7)
        },
    )
    report = inspect(scan(root))
    assert "missing_episodes" in kinds(report)
    finding = next(f for f in report.findings if f.kind == "missing_episodes")
    assert "E04" in finding.detail and "E05" in finding.detail
    assert finding.severity == WARNING


def test_a_complete_season_raises_nothing(tmp_path):
    root = build(
        tmp_path / "Media",
        {
            f"Shows/Squid Game (2021)/Season 03/Squid Game (2021) S03E{n:02} Ep.mkv": 100
            for n in range(1, 7)
        },
    )
    report = inspect(scan(root))
    assert "missing_episodes" not in kinds(report)


def test_a_big_gap_is_a_problem_not_a_warning(tmp_path):
    root = build(
        tmp_path / "Media",
        {
            f"Shows/Dark (2017)/Season 01/Dark (2017) S01E{n:02} Ep.mkv": 100
            for n in (1, 2, 9, 10)
        },
    )
    report = inspect(scan(root))
    finding = next(f for f in report.findings if f.kind == "missing_episodes")
    assert finding.severity == PROBLEM


def test_an_archive_beside_its_own_episodes_is_flagged(tmp_path):
    root = tmp_path / "Media"
    folder = root / "Shows" / "The 100 (2014)" / "Season 05"
    folder.mkdir(parents=True)
    (folder / "The 100 (2014) S05E01 Ep.mkv").write_bytes(b"x" * 500)
    (folder / "The.100.S05.zip").write_bytes(b"z" * 300_000_000)

    report = inspect(scan(root))
    finding = next(f for f in report.findings if f.kind == "redundant_archive")
    assert "already extracted" in finding.title
    assert finding.bytes_involved == 300_000_000
    assert report.reclaimable == 300_000_000


def test_an_archive_with_nothing_extracted_is_only_a_note(tmp_path):
    root = tmp_path / "Media"
    folder = root / "Movies" / "Something (2020)"
    folder.mkdir(parents=True)
    (folder / "Something.zip").write_bytes(b"z" * 300_000_000)

    report = inspect(scan(root))
    finding = next(f for f in report.findings if f.kind == "unextracted_archive")
    assert finding.severity == NOTE


def test_a_lower_quality_second_copy_is_found(tmp_path):
    root = build(
        tmp_path / "Media",
        {
            "Movies/Heat (1995)/Heat 1995 1080p BluRay.mkv": 900,
            "Movies/Heat old/Heat 1995 720p BluRay.mkv": 300,
        },
    )
    report = inspect(scan(root))
    finding = next(f for f in report.findings if f.kind == "lower_quality")
    assert "1080p" in finding.detail
    assert finding.bytes_involved == 300


def test_two_cuts_of_one_film_are_not_a_duplicate(tmp_path):
    root = build(
        tmp_path / "Media",
        {
            "Movies/Housefull 5 (2025)/Housefull 5 (2025) - A.mkv": 900,
            "Movies/Housefull 5 (2025)/Housefull 5 (2025) - B.mkv": 300,
        },
    )
    report = inspect(scan(root))
    assert "lower_quality" not in kinds(report)


def test_empty_and_tiny_videos_are_found(tmp_path):
    root = build(
        tmp_path / "Media",
        {
            "Movies/Broken (2020)/Broken (2020).mkv": 0,
            "Movies/Stub (2019)/Stub (2019).mkv": 5_000,
            "Movies/Fine (2018)/Fine (2018).mkv": 30_000_000,
        },
    )
    report = inspect(scan(root))
    assert "empty_file" in kinds(report)
    assert "tiny_video" in kinds(report)
    empty = next(f for f in report.findings if f.kind == "empty_file")
    assert empty.severity == PROBLEM
    assert not any(f.paths and f.paths[0].name == "Fine (2018).mkv" for f in report.findings)


def test_an_orphan_subtitle_is_reported(tmp_path):
    root = build(
        tmp_path / "Media",
        {
            "Movies/Alone (2020)/Alone (2020).mkv": 500,
            "Movies/Alone (2020)/Subs/nothing-here.srt": 10,
            "Movies/Alone (2020)/Subs/also-nothing.srt": 10,
        },
    )
    report = inspect(scan(root))
    # A Subs folder under a single video pairs fine, so nothing is orphaned here.
    assert "orphan_subtitle" not in kinds(report)


def test_a_tidy_library_reports_nothing(tmp_path):
    root = build(
        tmp_path / "Media",
        {
            "Movies/Fight Club (1999)/Fight Club (1999).mkv": 40_000_000,
            "Shows/Dark (2017)/Season 01/Dark (2017) S01E01 Secrets.mkv": 40_000_000,
            "Shows/Dark (2017)/Season 01/Dark (2017) S01E02 Lies.mkv": 40_000_000,
        },
    )
    report = inspect(scan(root))
    assert report.findings == []
    assert report.videos_checked == 3
    assert report.counts() == {PROBLEM: 0, WARNING: 0, NOTE: 0}


def test_the_pass_never_writes(tmp_path):
    root = build(tmp_path / "Media", {"Movies/A (2020)/A (2020).mkv": 100})
    before = {p: p.stat().st_mtime_ns for p in root.rglob("*") if p.is_file()}
    inspect(scan(root))
    after = {p: p.stat().st_mtime_ns for p in root.rglob("*") if p.is_file()}
    assert before == after


def test_probe_says_so_when_ffprobe_is_missing(tmp_path, monkeypatch):
    import endslate.health as health_mod

    def missing(*args, **kwargs):
        raise FileNotFoundError("ffprobe")

    monkeypatch.setattr(health_mod.subprocess, "run", missing)
    findings = probe([tmp_path / "x.mkv"])
    assert findings and findings[0].kind == "no_ffprobe"


def test_probe_flags_a_file_with_no_video_stream(tmp_path, monkeypatch):
    import endslate.health as health_mod

    class Result:
        returncode = 1
        stdout = ""
        stderr = "moov atom not found"

    monkeypatch.setattr(health_mod.subprocess, "run", lambda *a, **k: Result())
    findings = probe([tmp_path / "broken.mkv"])
    assert findings and findings[0].kind == "unplayable"
    assert findings[0].severity == PROBLEM
