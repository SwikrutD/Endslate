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
                out.add(op.dst.relative_to(plan.root).as_posix())
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


def test_downloads_mixes_movies_and_shows_and_keeps_unrecognized(tmp_path):
    root = tmp_path / "Media"
    (root / "Movies").mkdir(parents=True)
    (root / "Shows").mkdir()
    downloads = root / "Downloads"
    downloads.mkdir()
    (downloads / "Dune (2021) 1080p.mkv").write_bytes(b"movie")
    (downloads / "Dark S01E01 Secrets 1080p.mkv").write_bytes(b"show")
    (downloads / "notes.txt").write_text("leave me")

    plan = plan_for(root)
    found = targets(plan, Bucket.PLANNED)
    assert "Movies/Dune (2021)/Dune (2021).mkv" in found
    assert "Shows/Dark/Season 01/Dark S01E01 Secrets.mkv" in found
    assert not any("notes.txt" in target for target in targets(plan))


def test_extracted_download_archive_is_quarantined(tmp_path):
    root = tmp_path / "Media"
    (root / "Movies").mkdir(parents=True)
    (root / "Shows").mkdir()
    downloads = root / "Downloads"
    downloads.mkdir()
    (downloads / "Dune (2021) 1080p.mkv").write_bytes(b"movie")
    (downloads / "Dune (2021).zip").write_bytes(b"archive")

    plan = plan_for(root)
    archive = next(e for e in plan.by_bucket(Bucket.JUNK) if e.source_path and e.source_path.suffix == ".zip")
    assert archive.ops[0].kind is OpKind.QUARANTINE
    assert archive.target_path == root / "_Quarantine" / plan.quarantine_root.name / "Downloads" / "Dune (2021).zip"


def test_unextracted_download_archive_is_left_alone(tmp_path):
    root = tmp_path / "Media"
    (root / "Movies").mkdir(parents=True)
    (root / "Shows").mkdir()
    downloads = root / "Downloads"
    downloads.mkdir()
    (downloads / "Dune (2021).zip").write_bytes(b"archive")

    plan = plan_for(root)
    assert not any(e.source_path and e.source_path.name == "Dune (2021).zip" for e in plan.entries)


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


def _anime_library(tmp_path, files):
    root = tmp_path / "Media"
    for folder in ("Movies", "Shows", "Anime"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    for relative in files:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    return root


def test_anime_with_a_season_marker_is_planned_into_anime_offline(tmp_path):
    root = _anime_library(tmp_path, ["Anime/Shingeki no Kyojin/[Judas] Shingeki no Kyojin - S04E01.mkv"])
    found = targets(plan_for(root), Bucket.PLANNED)
    assert "Anime/Shingeki no Kyojin/Season 04/Shingeki no Kyojin S04E01.mkv" in found


def test_anime_counted_from_episode_one_waits_without_tvdb(tmp_path):
    root = _anime_library(tmp_path, ["Downloads/[SubsPlease] Sousou no Frieren - 12 (1080p).mkv"])
    plan = plan_for(root)
    entry = plan.by_bucket(Bucket.NEEDS_YOU)[0]
    assert entry.item.is_anime and entry.item.destination == "anime"
    assert "TheTVDB" in entry.reason


def test_a_film_in_the_anime_folder_goes_to_movies(tmp_path):
    root = _anime_library(tmp_path, ["Anime/Your Name (2016)/Your.Name.2016.1080p.BluRay.mkv"])
    found = targets(plan_for(root), Bucket.PLANNED)
    assert "Movies/Your Name (2016)/Your Name (2016).mkv" in found


def test_a_fansub_file_already_in_shows_stays_in_shows(tmp_path):
    root = _anime_library(tmp_path, ["Shows/Spy x Family/[SubsPlease] Spy x Family S2 - 05 (1080p).mkv"])
    found = targets(plan_for(root), Bucket.PLANNED)
    assert "Shows/Spy x Family/Season 02/Spy x Family S02E05.mkv" in found


def test_keeping_folder_names_keeps_the_anime_root(tmp_path):
    root = tmp_path / "Media"
    (root / "Anime Series" / "Dark").mkdir(parents=True)
    (root / "Anime Series" / "Dark" / "[Grp] Dark - S01E01.mkv").write_bytes(b"x")
    found = targets(plan_for(root, rename_top_level_folders=False), Bucket.PLANNED)
    assert any(t.startswith("Anime Series/") for t in found)
