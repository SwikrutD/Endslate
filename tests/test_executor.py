from pathlib import Path

from endslate.executor import execute, preflight, undo
from endslate.journal import Journal
from endslate.models import Bucket, OpKind, Operation
from endslate.planner import Options, build_plan
from endslate.presets import builtin
from endslate.scanner import scan

from tests.conftest import snapshot


def make_plan(root: Path, **kwargs):
    return build_plan(scan(root), builtin("Jellyfin"), Options(**kwargs))


def run(root: Path, tmp_path: Path, **kwargs):
    plan = make_plan(root, **kwargs)
    journal = Journal("test-run", path=tmp_path / "test-run.jsonl")
    return plan, execute(plan, "test-run", journal=journal)


def test_apply_then_undo_restores_everything(library, tmp_path):
    before = snapshot(library)
    plan, result = run(library, tmp_path)
    assert result.ok, result.failures
    assert result.moved > 0

    after = snapshot(library)
    assert set(before.values()) == set(after.values()), "file contents changed"
    assert set(before.keys()) != set(after.keys()), "nothing actually moved"

    undone = undo(tmp_path / "test-run.jsonl")
    assert undone.ok, undone.failures
    assert snapshot(library) == before


def test_apply_puts_files_where_the_plan_said(library, tmp_path):
    plan, result = run(library, tmp_path)
    assert result.ok, result.failures
    assert (library / "Movies/Fight Club (1999)/Fight Club (1999).mkv").exists()
    assert (library / "Shows/The 100/Season 01/The 100 S01E01 Pilot.mkv").exists()
    assert (library / "Movies/Baby Driver (2017)/Baby Driver (2017).en.srt").exists()
    assert not (library / "Movies/Fight Club").exists()


def test_nothing_is_deleted_only_quarantined(library, tmp_path):
    before = snapshot(library)
    plan, result = run(library, tmp_path)
    assert result.ok, result.failures
    after = snapshot(library)
    assert len(after) == len(before)
    quarantined = list((library / "_Quarantine").rglob("*"))
    assert any(p.name == "www.YTS.MX.jpg" for p in quarantined)
    assert any(p.name == "dan.srt" for p in quarantined)


def test_preflight_refuses_to_overwrite(library, tmp_path):
    plan = make_plan(library)
    victim = library / "Movies" / "Occupied.mkv"
    victim.parent.mkdir(parents=True, exist_ok=True)
    victim.write_bytes(b"x")
    plan.entries[0].ops = [Operation(OpKind.MOVE, library / "Movies" / "Rush Hour" / "Rush Hour.mkv", victim)]
    plan.entries[0].bucket = Bucket.PLANNED
    plan.entries[0].selected = True
    problems = preflight(plan)
    assert any("already exists" in p.message for p in problems)


def test_preflight_refuses_targets_outside_the_root(library, tmp_path):
    plan = make_plan(library)
    plan.entries[0].ops = [
        Operation(OpKind.MOVE, library / "Movies" / "Rush Hour" / "Rush Hour.mkv", tmp_path / "escaped.mkv")
    ]
    plan.entries[0].bucket = Bucket.PLANNED
    plan.entries[0].selected = True
    assert any("outside the library root" in p.message for p in preflight(plan))


def test_a_second_run_finds_nothing_left_to_do(library, tmp_path):
    plan, result = run(library, tmp_path)
    assert result.ok, result.failures
    second = make_plan(library)
    planned = second.by_bucket(Bucket.PLANNED)
    assert not planned, [str(e.source_path) for e in planned]


def test_undo_does_not_force_over_a_file_you_put_back(library, tmp_path):
    plan, result = run(library, tmp_path)
    assert result.ok
    (library / "Movies" / "Fight Club").mkdir(parents=True, exist_ok=True)
    blocker = library / "Movies/Fight Club/Fight.Club.1999.REMASTERED.1080p.BluRay.DDP5.1.x265-GalaxyRG265.mkv"
    blocker.write_bytes(b"mine")
    undone = undo(tmp_path / "test-run.jsonl")
    assert any("occupied" in p.message for p in undone.failures)
    assert blocker.read_bytes() == b"mine"
