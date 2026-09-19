"""Bugs found by running against the real library. One test per bug."""
from pathlib import Path

import pytest

from endslate import fsops
from endslate.cache import Cache
from endslate.matcher import TmdbMatcher
from endslate.models import Bucket, Confidence, FileKind, Item, ParsedName, ScannedFile
from endslate.planner import Options, build_plan
from endslate.presets import builtin
from endslate.scanner import scan

from tests.test_matcher import FakeSession, movie_item


# --------------------------------------------------------------- long paths


def test_raw_adds_the_extended_prefix_only_on_windows(monkeypatch):
    monkeypatch.setattr(fsops, "WINDOWS", True)
    assert fsops.raw("C:\\a\\b").startswith("\\\\?\\")
    assert fsops.raw("\\\\?\\C:\\a").count("\\\\?\\") == 1
    monkeypatch.setattr(fsops, "WINDOWS", False)
    assert fsops.raw("/tmp/x") == "/tmp/x"


def test_unraw_is_the_inverse():
    assert fsops.unraw("\\\\?\\C:\\a\\b") == "C:\\a\\b"
    assert fsops.unraw("\\\\?\\UNC\\server\\share") == "\\\\server\\share"
    assert fsops.unraw("/tmp/x") == "/tmp/x"


def test_a_deeply_nested_source_still_plans_and_moves(tmp_path):
    """Dune sat 352 characters deep and its move failed silently on Windows."""
    root = tmp_path / "Media"
    long_name = "Dune - Part One (2021) 1080p BluRay 10bit HEVC [Hindi DDP 5.1   English DDP 7.1] x265 (DarQ-LUMiX) 4KHDHub.com"
    nested = root / "Movies" / long_name / long_name
    nested.mkdir(parents=True)
    (nested / f"{long_name}.mkv").write_bytes(b"x" * 100)

    plan = build_plan(scan(root), builtin("Jellyfin"), Options())
    planned = plan.by_bucket(Bucket.PLANNED)
    assert len(planned) == 1
    assert planned[0].target_path.name == "Dune - Part One (2021).mkv"

    from endslate.executor import execute
    from endslate.journal import Journal

    result = execute(plan, "long", journal=Journal("long", path=tmp_path / "long.jsonl"))
    assert result.ok, result.failures
    assert (root / "Movies" / "Dune - Part One (2021)" / "Dune - Part One (2021).mkv").exists()


# ------------------------------------------------------------ case renames


def test_move_handles_a_rename_that_only_changes_case(tmp_path):
    source = tmp_path / "IT (2017).mkv"
    source.write_bytes(b"x")
    target = tmp_path / "It (2017).mkv"
    fsops.move(source, target)
    names = [p.name for p in tmp_path.iterdir()]
    assert names == ["It (2017).mkv"]
    assert not any(n.endswith(fsops.TEMP_SUFFIX) for n in names)


def test_actual_name_reports_the_spelling_on_disk(tmp_path):
    (tmp_path / "IT (2017)").mkdir()
    assert fsops.actual_name(tmp_path / "It (2017)") == "IT (2017)"
    assert fsops.actual_name(tmp_path / "Missing") == "Missing"


# ------------------------------------------------------------ year scoring


def test_the_right_year_wins_even_when_tmdb_lists_it_second(tmp_path):
    """Two films called The Witch. Capping the score at 1.0 lost the year."""
    session = FakeSession(movies={"The Witch": [
        {"id": 2, "title": "The Witch", "release_date": "2016-02-19"},
        {"id": 1, "title": "The Witch", "release_date": "2015-01-27"},
    ]})
    matcher = TmdbMatcher("key", cache=Cache(tmp_path / "c.sqlite"), session=session)
    item = movie_item("The Witch", 2015)
    matcher.match_all([item])
    assert item.confidence is Confidence.HIGH
    assert item.meta.year == 2015
    assert item.meta.tmdb_id == 1


def test_a_wrong_year_candidate_scores_below_a_right_one(tmp_path):
    matcher = TmdbMatcher("", cache=Cache(tmp_path / "c.sqlite"))
    from endslate.models import Candidate

    right = Candidate(title="The Witch", year=2015, tmdb_id=1)
    near = Candidate(title="The Witch", year=2016, tmdb_id=2)
    far = Candidate(title="The Witch", year=1997, tmdb_id=3)
    assert matcher._score("The Witch", 2015, right) > matcher._score("The Witch", 2015, near)
    assert matcher._score("The Witch", 2015, near) > matcher._score("The Witch", 2015, far)


# ------------------------------------------------------------- idempotency


CLEAN = [
    "Movies/Fight Club (1999)/Fight Club (1999).mkv",
    "Movies/Dune - Part One (2021)/Dune - Part One (2021).mkv",
    "Shows/The 100 (2014)/Season 03/The 100 (2014) S03E14 Red Sky at Morning.mkv",
    "Shows/The 100 (2014)/Season 02/The 100 (2014) S02E15 Blood Must Have Blood (1).mkv",
    "Shows/Modern Family (2009)/Season 01/Modern Family (2009) S01E22 Airport 2010.mkv",
    "Shows/Modern Family (2009)/Season 10/Modern Family (2009) S10E16 Red Alert.mkv",
    "Shows/Gravity Falls (2012)/Season 01/Gravity Falls (2012) S01E19 Dreamscaperers (1).mp4",
]


def test_already_correct_names_are_left_alone(tmp_path):
    root = tmp_path / "Media"
    for relative in CLEAN:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * 10)

    plan = build_plan(scan(root), builtin("Jellyfin"), Options())
    planned = plan.by_bucket(Bucket.PLANNED)
    assert not planned, [f"{e.source_path.name} -> {e.target_path.name}" for e in planned]
    assert len(plan.by_bucket(Bucket.NOOP)) == len(CLEAN)
