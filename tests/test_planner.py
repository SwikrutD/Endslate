from pathlib import Path

from endslate.models import Bucket, OpKind
from endslate.planner import Options, build_plan
from endslate.presets import builtin
from endslate.scanner import scan


def plan_for(root: Path, preset="Jellyfin", **kwargs):
    return build_plan(scan(root), builtin(preset), Options(**kwargs))


def targets(plan, bucket=None):
    out = set()
    for entry in plan.entries:
        if bucket is not None and entry.bucket is not bucket:
            continue
        for op in entry.ops:
            if op.kind in (OpKind.MOVE, OpKind.QUARANTINE) and op.dst is not None:
                out.add(str(op.dst.relative_to(plan.root)))
    return out


def test_shapes_all_resolve(library):
    plan = plan_for(library)
    found = targets(plan)
    expected = {
        "Movies/American Psycho (2000)/American Psycho (2000).mkv",
        "Movies/Fight Club (1999)/Fight Club (1999).mkv",
        "Movies/Baby Driver (2017)/Baby Driver (2017).mp4",
        "Movies/Dune - Part One (2021)/Dune - Part One (2021).mkv",
        "Movies/The Hangover (2009)/The Hangover (2009).mp4",
        "Movies/The Hangover Part II (2011)/The Hangover Part II (2011).mp4",
        "Movies/Housefull 5 (2025)/Housefull 5 (2025) - A.mkv",
        "Movies/Housefull 5 (2025)/Housefull 5 (2025) - B.mkv",
        "Shows/The 100/Season 01/The 100 S01E01 Pilot.mkv",
        "Shows/Dark/Season 01/Dark S01E01 Secrets.mkv",
        "Shows/Squid Game/Season 03/Squid Game S03E01 Keys and Knives.mkv",
        "Shows/Modern Family (2009)/Season 01/Modern Family (2009) S01E01 Pilot.mkv",
    }
    assert expected <= found


def test_collection_folder_is_flattened(library):
    plan = plan_for(library)
    found = targets(plan)
    assert "Movies/The Hangover (2009)/The Hangover (2009).mp4" in found
    planned = targets(plan, Bucket.PLANNED)
    assert not any("The Hangover/The Hangover" in t for t in planned)


def test_self_nested_folder_collapses(library):
    plan = plan_for(library)
    dune = [t for t in targets(plan, Bucket.PLANNED) if "Dune" in t]
    assert dune == ["Movies/Dune - Part One (2021)/Dune - Part One (2021).mkv"]


def test_subtitles_follow_their_video(library):
    plan = plan_for(library)
    found = targets(plan)
    assert "Movies/Baby Driver (2017)/Baby Driver (2017).en.srt" in found
    assert "Shows/Dark/Season 01/Dark S01E01 Secrets.en.srt" in found


def test_foreign_subtitles_are_quarantined_not_deleted(library):
    plan = plan_for(library)
    quarantined = [
        e for e in plan.by_bucket(Bucket.JUNK)
        if e.source_path and e.source_path.name in ("dan.srt", "Latin American.spa.srt")
    ]
    assert len(quarantined) == 2
    for entry in quarantined:
        assert entry.ops[0].kind is OpKind.QUARANTINE
        assert "_Quarantine" in str(entry.target_path)


def test_junk_folder_moves_whole(library):
    plan = plan_for(library)
    names = [e.source_path.name for e in plan.by_bucket(Bucket.JUNK) if e.source_path]
    assert "jquery.min" in names
    assert "._Black Panther 2018 1080p.mp4" in names
    assert "www.YTS.MX.jpg" in names
    assert "desktop.ini" in names


def test_year_less_movie_needs_you(library):
    plan = plan_for(library)
    needs = [e.source_path.name for e in plan.by_bucket(Bucket.NEEDS_YOU)]
    assert "Rush Hour.mkv" in needs


def test_already_correct_is_a_noop(library):
    plan = plan_for(library)
    noop = [e.source_path.name for e in plan.by_bucket(Bucket.NOOP)]
    assert "Real Steel (2011).avi" in noop


def test_flat_preset_drops_the_movie_folder(library):
    plan = plan_for(library, preset="Flat")
    assert "Movies/Fight Club (1999).mkv" in targets(plan)


def test_plex_preset_uses_dashes(library):
    plan = plan_for(library, preset="Plex")
    assert "Shows/The 100/Season 01/The 100 - s01e01 - Pilot.mkv" in targets(plan)


def test_keeping_folder_names_leaves_tv_shows_alone(library):
    plan = plan_for(library, rename_top_level_folders=False)
    assert any(t.startswith("TV Shows/") for t in targets(plan))


def test_nothing_targets_outside_the_root(library):
    plan = plan_for(library)
    for entry in plan.entries:
        for op in entry.ops:
            if op.dst is not None:
                assert str(op.dst).startswith(str(library))
