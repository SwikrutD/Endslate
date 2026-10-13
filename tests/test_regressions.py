"""Bugs found by running against the real library. One test per bug."""
from pathlib import Path

import pytest

from endslate import fsops
from endslate.cache import Cache
from endslate.matcher import TmdbMatcher
from endslate.models import Bucket, Confidence, FileKind, Item, OpKind, ParsedName, ScannedFile
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


# ------------------------------------------------------- reading our own output


def test_a_part_marker_we_wrote_is_read_back(tmp_path):
    """Housefull 5 A and B came back as a duplicate pair on the second scan."""
    from endslate.models import Bucket
    from endslate.parser import parse

    assert parse("Housefull 5 (2025) - A.mkv").part == "A"
    assert parse("Housefull 5 (2025) - B.mkv").part == "B"
    assert parse("Dune - Part One (2021).mkv").part == ""
    assert parse("Dune - Part One (2021).mkv").title == "Dune - Part One"

    root = tmp_path / "Media"
    folder = root / "Movies" / "Housefull 5 (2025)"
    folder.mkdir(parents=True)
    (folder / "Housefull 5 (2025) - A.mkv").write_bytes(b"a" * 40)
    (folder / "Housefull 5 (2025) - B.mkv").write_bytes(b"b" * 20)

    plan = build_plan(scan(root), builtin("Jellyfin"), Options())
    assert not plan.by_bucket(Bucket.DUPLICATE)
    assert len(plan.by_bucket(Bucket.NOOP)) == 2


# ----------------------------------------------------------------- duplicates


def _duplicate_library(tmp_path):
    root = tmp_path / "Media"
    for folder, name, size in (
        ("My Big Fat Greek Wedding 2", "My Big Fat Greek Wedding 2 2016.mp4", 400),
        ("My Big Fat Greek Wedding 2 2016", "My Big Fat Greek Wedding 2 2016.mp4", 900),
    ):
        path = root / "Movies" / folder
        path.mkdir(parents=True)
        (path / name).write_bytes(b"x" * size)
    return root


def test_a_duplicate_can_be_resolved_by_keeping_one(tmp_path):
    from endslate.models import Bucket
    from endslate.planner import keep_one_of_duplicates

    plan = build_plan(scan(_duplicate_library(tmp_path)), builtin("Jellyfin"), Options())
    group = plan.by_bucket(Bucket.DUPLICATE)
    assert len(group) == 2

    moved = keep_one_of_duplicates(plan, group[0])
    assert moved == 1
    assert group[0].bucket is Bucket.PLANNED
    assert group[1].bucket is Bucket.JUNK
    assert "_Quarantine" in str(group[1].target_path)
    assert group[1].ops[0].kind.value == "quarantine"
    assert not plan.by_bucket(Bucket.DUPLICATE)


def test_keeping_the_largest_resolves_every_group(tmp_path):
    from endslate.models import Bucket
    from endslate.planner import keep_largest_duplicates

    plan = build_plan(scan(_duplicate_library(tmp_path)), builtin("Jellyfin"), Options())
    assert keep_largest_duplicates(plan) == 1
    kept = [e for e in plan.entries if e.bucket is Bucket.PLANNED]
    assert len(kept) == 1
    assert kept[0].item.video.size == 900
    assert not plan.by_bucket(Bucket.DUPLICATE)


def test_nothing_is_deleted_when_resolving_a_duplicate(tmp_path):
    from endslate.models import Bucket, OpKind
    from endslate.planner import keep_largest_duplicates

    plan = build_plan(scan(_duplicate_library(tmp_path)), builtin("Jellyfin"), Options())
    keep_largest_duplicates(plan)
    for entry in plan.entries:
        for op in entry.ops:
            assert op.kind in (OpKind.MKDIR, OpKind.MOVE, OpKind.QUARANTINE)


# --------------------------------------------------------- provider outage


def test_an_unreachable_provider_falls_back_to_the_filename(tmp_path):
    """A network outage was silently pushing every title into Needs you."""
    from endslate.cache import Cache
    from endslate.matcher import TmdbMatcher
    from endslate.models import Confidence

    class DeadSession:
        def get(self, *args, **kwargs):
            raise OSError("getaddrinfo failed")

    matcher = TmdbMatcher("key", cache=Cache(tmp_path / "c.sqlite"), session=DeadSession())
    items = [movie_item("Fight Club", 1999), movie_item("Rush Hour")]
    matcher.match_all(items)

    assert matcher.unreachable
    assert items[0].confidence is Confidence.HIGH
    assert "unreachable" in items[0].note
    assert items[1].confidence is Confidence.LOW


# ----------------------------------------------------- matching, from recordings


def test_dark_is_not_confused_with_the_dark(tmp_path):
    from tests.test_matcher import episode_item

    session = FakeSession(
        shows={
            "Dark": [
                {"id": 1, "name": "The Dark", "first_air_date": "2026-01-01"},
                {"id": 70523, "name": "Dark", "first_air_date": "2017-12-01"},
            ]
        },
        episodes={(70523, 1): {1: "Secrets"}},
    )
    matcher = TmdbMatcher("k", cache=Cache(tmp_path / "c.sqlite"), session=session)
    item = episode_item("Dark", 1, 1)
    matcher.match_all([item])
    assert item.confidence is Confidence.HIGH, item.note
    assert item.meta.tmdb_id == 70523
    assert item.meta.episode_title == "Secrets"


def test_a_subtitle_tmdb_drops_still_matches_when_the_year_agrees(tmp_path):
    session = FakeSession(
        movies={"Dune - Part One": [{"id": 438631, "title": "Dune", "release_date": "2021-09-15"}]}
    )
    matcher = TmdbMatcher("k", cache=Cache(tmp_path / "c.sqlite"), session=session)
    item = movie_item("Dune - Part One", 2021)
    matcher.match_all([item])
    assert item.confidence in (Confidence.HIGH, Confidence.MEDIUM), item.note
    assert item.meta.tmdb_id == 438631


def test_a_subtitle_is_not_dropped_when_the_year_disagrees(tmp_path):
    session = FakeSession(
        movies={
            "Mission Impossible - Dead Reckoning": [
                {"id": 954, "title": "Mission: Impossible", "release_date": "1996-05-22"}
            ]
        }
    )
    matcher = TmdbMatcher("k", cache=Cache(tmp_path / "c.sqlite"), session=session)
    item = movie_item("Mission Impossible - Dead Reckoning", 2023)
    matcher.match_all([item])
    assert item.confidence is Confidence.LOW


# ------------------------------------------------- found while adding anime


def _media(tmp_path, files):
    root = tmp_path / "Media"
    for folder in ("Movies", "Shows"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    for relative, size in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
    return root


def test_a_leading_release_group_is_not_part_of_the_title():
    """"[SubsPlease] Frieren - 12" parsed as a show called "SubsPlease] Frieren - 12"."""
    from endslate.parser import parse

    parsed = parse("[SubsPlease] Sousou no Frieren - 12 (1080p) [A1B2C3D4].mkv")
    assert parsed.title == "Sousou no Frieren"
    assert parsed.release_group == "SubsPlease"


def test_no_in_a_title_does_not_make_an_english_subtitle_norwegian(tmp_path):
    """Sousou no Frieren and Point of No Return read as Norwegian, and with
    English-only on their only subtitle went to quarantine."""
    root = _media(tmp_path, {
        "Movies/Point of No Return (1993)/Point of No Return (1993).mkv": 10,
        "Movies/Point of No Return (1993)/Point of No Return (1993).srt": 1,
    })
    plan = build_plan(scan(root), builtin("Jellyfin"), Options(english_only_subtitles=True))
    quarantined = [op.src.name for e in plan.entries for op in e.ops
                   if op.kind is OpKind.QUARANTINE and op.src is not None]
    assert "Point of No Return (1993).srt" not in quarantined


def test_a_two_episode_file_keeps_its_second_number(tmp_path):
    """S01E01E02 was renamed S01E01, so the media server lost episode two."""
    root = _media(tmp_path, {"Shows/Dark/Dark.S01E01E02.1080p.mkv": 10})
    plan = build_plan(scan(root), builtin("Jellyfin"), Options())
    target = plan.by_bucket(Bucket.PLANNED)[0].target_path.name
    assert "S01E01-E02" in target
    plex = build_plan(scan(root), builtin("Plex"), Options())
    assert "s01e01-e02" in plex.by_bucket(Bucket.PLANNED)[0].target_path.name


def test_an_archive_outside_downloads_is_never_swept_up(tmp_path):
    """With a Downloads folder present, every archive next to a video anywhere
    in the library was planned for quarantine."""
    root = _media(tmp_path, {
        "Movies/Dune (2021)/Dune (2021).mkv": 10,
        "Movies/Dune (2021)/Dune (2021).zip": 10,
        "Downloads/Dark S01E01.mkv": 10,
    })
    plan = build_plan(scan(root), builtin("Jellyfin"), Options())
    assert not any(e.source_path and e.source_path.suffix == ".zip" for e in plan.entries)


def test_a_loose_archive_in_downloads_needs_its_own_video(tmp_path):
    """Any video in Downloads sent every loose archive there to quarantine."""
    root = _media(tmp_path, {
        "Downloads/Dark S01E01 Secrets.mkv": 10,
        "Downloads/Dune (2021).zip": 10,
        "Downloads/Arrival (2016).mkv": 10,
        "Downloads/Arrival (2016).rar": 10,
    })
    plan = build_plan(scan(root), builtin("Jellyfin"), Options())
    archived = {e.source_path.name for e in plan.by_bucket(Bucket.JUNK) if e.source_path}
    assert "Arrival (2016).rar" in archived
    assert "Dune (2021).zip" not in archived


def test_the_second_copy_of_a_film_keeps_its_candidates(tmp_path):
    """The lookup was shared but the answer was not: the second copy reached
    Needs you with nothing to choose from."""
    session = FakeSession(movies={"Beauty And The Beast": [
        {"id": 1, "title": "Beauty and the Beast", "release_date": "1991-11-22"},
        {"id": 2, "title": "Beauty and the Beast", "release_date": "2017-03-16"},
    ], "Fight Club": [{"id": 550, "title": "Fight Club", "release_date": "1999-10-15"}]})
    matcher = TmdbMatcher("k", cache=Cache(tmp_path / "c.sqlite"), session=session)
    first, second = movie_item("Beauty And The Beast"), movie_item("Beauty And The Beast")
    club, club_again = movie_item("Fight Club", 1999), movie_item("Fight Club", 1999)
    matcher.match_all([first, second, club, club_again])
    assert len(second.candidates) == len(first.candidates) == 2
    assert second.note == first.note
    assert club_again.confidence is club.confidence is Confidence.HIGH


def test_a_rate_limit_that_never_lifts_does_not_recurse_forever(tmp_path, monkeypatch):
    import endslate.matcher as matcher_mod

    class Limited:
        calls = 0

        def get(self, *args, **kwargs):
            Limited.calls += 1

            class R:
                status_code = 429
            return R()

    monkeypatch.setattr(matcher_mod.time, "sleep", lambda _s: None)
    matcher = TmdbMatcher("k", cache=Cache(tmp_path / "c.sqlite"), session=Limited())
    assert matcher.search_movie("Fight Club", None) == []
    assert Limited.calls == matcher_mod.MAX_RETRIES + 1
    assert "429" in matcher.offline_reason


def test_a_subtitle_two_episodes_could_own_is_left_alone(tmp_path):
    """In a folder of episodes, an unnumbered subtitle went to the first one."""
    root = _media(tmp_path, {
        "Shows/Dark/Season 1/Dark S01E01.mkv": 10,
        "Shows/Dark/Season 1/Dark S01E02.mkv": 10,
        "Shows/Dark/Season 1/Dark.en.srt": 1,
    })
    plan = build_plan(scan(root), builtin("Jellyfin"), Options())
    owners = [e for e in plan.entries if e.item is not None and e.item.subtitles]
    assert owners == []


def test_jellyfin_reports_every_page_of_a_big_library():
    """One request capped at 10,000 rows; the rest of the library went unreported."""
    from endslate import jellyfin
    from endslate.jellyfin import JellyfinClient

    rows = [{"Name": f"Episode {n}", "Type": "Episode", "Path": f"Z:/none/{n}.mkv",
             "ProviderIds": {}} for n in range(jellyfin.PAGE_SIZE * 2 + 5)]
    rows.append({"Name": "Dark", "Type": "Series", "Path": "Z:/none", "ProviderIds": {"Tvdb": "1"}})

    class Server:
        def request(self, method, url, params=None, headers=None, timeout=None):
            start = int(params.get("startIndex", 0))
            page = rows[start:start + int(params["limit"])]

            class R:
                status_code = 200

                def json(self_inner):
                    return {"Items": page, "TotalRecordCount": len(rows)}
            return R()

    report = JellyfinClient("http://localhost:8096", "key", session=Server()).report()
    assert report.total == 1 and report.identified == 1


def test_undo_with_no_run_named_skips_runs_already_undone(tmp_path, monkeypatch, capsys):
    from endslate import cli
    from endslate.journal import RunInfo

    reverted = RunInfo("new", tmp_path / "new.jsonl", "2026-10-02", "M:/Media", "Jellyfin", 3, True, True)
    standing = RunInfo("old", tmp_path / "old.jsonl", "2026-10-01", "M:/Media", "Jellyfin", 3, True, False)
    undone = []

    import endslate.executor as executor_mod
    import endslate.journal as journal_mod
    from endslate.executor import Result

    monkeypatch.setattr(journal_mod, "list_runs", lambda: [reverted, standing])
    monkeypatch.setattr(journal_mod, "mark_reverted", lambda path: None)
    monkeypatch.setattr(executor_mod, "undo", lambda path: undone.append(path.stem) or Result())
    assert cli.main(["undo"]) == 0
    assert undone == ["old"]
    assert cli.main(["undo", "new"]) == 2


def test_a_subtitle_already_in_place_is_not_called_redundant(tmp_path):
    """On the real library every correctly named subtitle was proposed for
    _Quarantine as redundant, because a file that does not move was never
    marked as kept."""
    root = _media(tmp_path, {
        "Shows/Gravity Falls (2012)/Season 02/Gravity Falls (2012) S02E14 The Stanchurian Candidate.mp4": 10,
        "Shows/Gravity Falls (2012)/Season 02/Gravity Falls (2012) S02E14 The Stanchurian Candidate.en.sdh.srt": 1,
        "Shows/Gravity Falls (2012)/Season 02/Gravity Falls (2012) S02E15 The Last Mabelcorn.mp4": 10,
        "Shows/Gravity Falls (2012)/Season 02/Gravity Falls (2012) S02E15 The Last Mabelcorn.en.srt": 1,
    })
    plan = build_plan(scan(root), builtin("Jellyfin"), Options(english_only_subtitles=True))
    assert plan.by_bucket(Bucket.JUNK) == []


def test_the_subtitle_of_a_file_waiting_on_you_stays_with_it(tmp_path):
    root = _media(tmp_path, {
        "Movies/Rush Hour/Rush Hour.mkv": 10,
        "Movies/Rush Hour/Rush Hour.srt": 1,
    })
    plan = build_plan(scan(root), builtin("Jellyfin"), Options(english_only_subtitles=True))
    assert plan.by_bucket(Bucket.NEEDS_YOU)
    assert plan.by_bucket(Bucket.JUNK) == []


def test_a_second_english_track_is_still_redundant(tmp_path):
    root = _media(tmp_path, {
        "Movies/Baby Driver/Baby Driver 2017.mp4": 10,
        "Movies/Baby Driver/Baby Driver 2017.srt": 5,
        "Movies/Baby Driver/Subs/English.srt": 3,
    })
    plan = build_plan(scan(root), builtin("Jellyfin"), Options(english_only_subtitles=True))
    junk = [e.source_path.name for e in plan.by_bucket(Bucket.JUNK)]
    assert junk == ["English.srt"]


def test_a_show_is_searched_by_its_title_not_its_folder_name(tmp_path):
    """3 Body Problem (2024) went to Needs you with "no TMDB result": the
    search sent the folder name, year and brackets included."""
    session = FakeSession(
        shows={"3 Body Problem": [{"id": 108545, "name": "3 Body Problem", "first_air_date": "2024-03-21"}]},
        episodes={(108545, 1): {1: "Countdown"}},
    )
    matcher = TmdbMatcher("k", cache=Cache(tmp_path / "c.sqlite"), session=session)
    parsed = ParsedName(title="3 Body Problem", year=2024, season=1, episode=1)
    video = ScannedFile(path=Path("/library/Shows/3 Body Problem (2024)/Season 01/x.mkv"), size=1, kind=FileKind.VIDEO)
    item = Item(video=video, is_tv=True, show_hint="3 Body Problem (2024)", parsed=parsed)
    matcher.match_all([item])
    assert item.confidence is Confidence.HIGH, item.note
    assert item.meta.episode_title == "Countdown"
