"""Anime against TheTVDB, replayed from responses it really gave.

scripts/record_tvdb.py writes tests/fixtures/tvdb/responses.json. Everything
here runs offline against that recording, or against a stub where the point is
behaviour the recording cannot show (a bad key, an outage).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from endslate.cache import Cache
from endslate.matching import Resolver, match_items
from endslate.models import Bucket, Confidence, FileKind, Item, ParsedName, ScannedFile
from endslate.planner import Options, build_plan
from endslate.presets import builtin
from endslate.scanner import scan
from endslate.tvdb import API, TvdbError, TvdbMatcher, tvdb_language

FIXTURE = Path(__file__).parent / "fixtures" / "tvdb" / "responses.json"


class Reply:
    def __init__(self, payload, status=200):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


class ReplaySession:
    """TheTVDB as recorded. Anything not in the recording is a 404, and noted."""

    def __init__(self, recorded: dict, key: str = "recorded"):
        self.recorded = recorded
        self.key = key
        self.logins = 0
        self.gets: list[str] = []
        self.misses: list[str] = []

    def post(self, url, json=None, timeout=None):
        self.logins += 1
        if (json or {}).get("apikey") != self.key:
            return Reply({"status": "failure"}, 401)
        return Reply({"data": {"token": "token"}})

    def get(self, url, params=None, headers=None, timeout=None):
        path = url[len(API):]
        params = params or {}
        key = path + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        self.gets.append(key)
        if key in self.recorded:
            return Reply(self.recorded[key])
        self.misses.append(key)
        return Reply({"status": "failure"}, 404)


@pytest.fixture(scope="module")
def recorded():
    if not FIXTURE.exists():
        pytest.skip("no recorded TheTVDB responses, run scripts/record_tvdb.py")
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def session(recorded):
    return ReplaySession(recorded)


@pytest.fixture
def tvdb(session, tmp_path):
    return TvdbMatcher("recorded", cache=Cache(tmp_path / "tvdb.sqlite"), session=session)


def library(tmp_path: Path, files: dict[str, int]) -> Path:
    root = tmp_path / "Media"
    for folder in ("Movies", "Shows"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    for relative, size in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
    return root


def plan_with(root: Path, tvdb, tmdb=None):
    return build_plan(scan(root), builtin("Jellyfin"), Options(),
                      matcher=lambda items: match_items(items, tmdb=tmdb, tvdb=tvdb))


def planned_targets(plan) -> dict[str, str]:
    return {
        entry.source_path.name: entry.target_path.relative_to(plan.root).as_posix()
        for entry in plan.by_bucket(Bucket.PLANNED)
    }


def episode_at(recorded, series_id: int, absolute: int) -> tuple[int, int, str]:
    for key, payload in recorded.items():
        if key.startswith(f"/series/{series_id}/episodes/"):
            for e in payload["data"]["episodes"]:
                if e["absoluteNumber"] == absolute and e["seasonNumber"]:
                    return e["seasonNumber"], e["number"], e["name"]
    raise AssertionError(f"episode {absolute} of {series_id} is not in the recording")


# ------------------------------------------------------------------ language


def test_the_metadata_language_becomes_a_three_letter_code():
    assert tvdb_language("en-US") == "eng"
    assert tvdb_language("de-DE") == "deu"
    assert tvdb_language("xx") == "eng"


# ------------------------------------------------------------------- replay


def test_a_fansub_episode_in_downloads_lands_in_anime_with_its_tvdb_id(tmp_path, tvdb, recorded):
    root = library(tmp_path, {"Downloads/[SubsPlease] Sousou no Frieren - 12 (1080p) [A1B2C3D4].mkv": 10})
    plan = plan_with(root, tvdb)
    season, number, name = episode_at(recorded, 424536, 12)
    target = planned_targets(plan)["[SubsPlease] Sousou no Frieren - 12 (1080p) [A1B2C3D4].mkv"]
    show = "Frieren - Beyond Journey's End (2023) [tvdbid-424536]"
    assert target.startswith(f"Anime/{show}/Season {season:02}/")
    assert f"S{season:02}E{number:02}" in target
    assert name.split("'")[0] in target


def test_one_piece_counted_from_episode_one_finds_its_season(tmp_path, tvdb, recorded):
    root = library(tmp_path, {"Anime/One Piece/[Erai-raws] One Piece - 1085 [1080p][Multiple Subtitle].mkv": 10})
    plan = plan_with(root, tvdb)
    season, number, _name = episode_at(recorded, 81797, 1085)
    entry = plan.entries[0]
    assert entry.bucket is Bucket.PLANNED, entry.reason
    # The live-action ONE PIECE (2023) is exactly "One Piece" too. The anime
    # wins because the release is anime, not because it was listed first.
    assert entry.item.meta.tvdb_id == 81797
    assert entry.item.year == 1999
    assert f"S{season:02}E{number:02}" in entry.target_path.name


def test_a_season_marker_in_a_fansub_name_is_kept(tmp_path, tvdb):
    root = library(tmp_path, {"Downloads/[SubsPlease] Spy x Family S2 - 05 (1080p) [ABCDEF12].mkv": 10})
    plan = plan_with(root, tvdb)
    entry = plan.entries[0]
    assert entry.bucket is Bucket.PLANNED, entry.reason
    assert entry.item.meta.tvdb_id == 405920
    assert "S02E05" in entry.target_path.name


def test_a_romaji_title_matches_its_english_one(tmp_path, tvdb):
    root = library(tmp_path, {"Anime/Shingeki no Kyojin/[Judas] Shingeki no Kyojin - S04E01.mkv": 10})
    plan = plan_with(root, tvdb)
    entry = plan.entries[0]
    assert entry.bucket is Bucket.PLANNED, entry.reason
    assert entry.item.title == "Attack on Titan"
    assert entry.target_path.relative_to(plan.root).as_posix().startswith(
        "Anime/Attack on Titan (2013) [tvdbid-267440]/Season 04/"
    )


def test_two_anime_with_one_name_ask_rather_than_guess(tmp_path, tvdb):
    """Mob Psycho 100 is a 2016 anime and a 2018 live-action drama, both Japanese."""
    root = library(tmp_path, {"Downloads/[HorribleSubs] Mob Psycho 100 - 05 [720p].mkv": 10})
    plan = plan_with(root, tvdb)
    entry = plan.entries[0]
    assert entry.bucket is Bucket.NEEDS_YOU
    assert {c.tvdb_id for c in entry.item.candidates} >= {307375, 337829}


def test_a_folder_that_names_its_tvdb_id_needs_no_search(tmp_path, tvdb, session):
    root = library(tmp_path, {
        "Anime/Frieren - Beyond Journey's End (2023) [tvdbid-424536]/Season 01/"
        "Frieren - Beyond Journey's End (2023) S01E03 Killing Magic.mkv": 10,
    })
    plan = plan_with(root, tvdb)
    entry = plan.entries[0]
    assert not any(key.startswith("/search") for key in session.gets)
    assert entry.item.confidence is Confidence.HIGH
    assert entry.item.meta.tvdb_id == 424536


def test_an_episode_tvdb_does_not_have_yet_waits(tmp_path, tvdb):
    root = library(tmp_path, {"Anime/Sousou no Frieren/[SubsPlease] Sousou no Frieren - 400 (1080p).mkv": 10})
    plan = plan_with(root, tvdb)
    entry = plan.entries[0]
    assert entry.bucket is Bucket.NEEDS_YOU
    assert "400" in entry.reason


def test_anime_subtitles_go_to_their_own_episode(tmp_path, tvdb):
    root = library(tmp_path, {
        "Anime/Sousou no Frieren/[SubsPlease] Sousou no Frieren - 01 (1080p).mkv": 10,
        "Anime/Sousou no Frieren/[SubsPlease] Sousou no Frieren - 02 (1080p).mkv": 10,
        "Anime/Sousou no Frieren/[SubsPlease] Sousou no Frieren - 02 (1080p).en.ass": 1,
    })
    plan = plan_with(root, tvdb)
    owner = next(e for e in plan.entries
                 if e.item is not None and any(s.path.suffix == ".ass" for s in e.item.subtitles))
    assert "- 02" in owner.item.video.path.name
    sub_target = next(op.dst for op in owner.ops if op.src is not None and op.src.suffix == ".ass")
    assert "E02" in sub_target.name and sub_target.name.endswith(".en.ass")


def test_the_recording_answered_everything(tmp_path, tvdb, session):
    root = library(tmp_path, {
        "Downloads/[SubsPlease] Sousou no Frieren - 12 (1080p).mkv": 10,
        "Anime/One Piece/[Erai-raws] One Piece - 1085 [1080p].mkv": 10,
    })
    plan_with(root, tvdb)
    assert session.misses == []


# -------------------------------------------------------------------- stubs


def anime_item(name: str) -> Item:
    from endslate.parser import parse

    parsed = parse(name, anime=True)
    video = ScannedFile(path=Path(f"/library/Anime/{parsed.title}/{name}"), size=1, kind=FileKind.VIDEO)
    return Item(video=video, is_tv=True, is_anime=True, section="anime",
                show_hint=parsed.title, parsed=parsed)


def test_without_a_tvdb_key_an_absolute_number_waits_with_a_reason():
    item = anime_item("[SubsPlease] Sousou no Frieren - 12 (1080p).mkv")
    match_items([item], tmdb=None, tvdb=None)
    assert item.confidence is Confidence.LOW
    assert "TheTVDB key" in item.note


def test_a_rejected_key_says_so(tmp_path):
    session = ReplaySession({}, key="the right one")
    matcher = TvdbMatcher("wrong", cache=Cache(tmp_path / "c.sqlite"), session=session)
    with pytest.raises(TvdbError, match="rejected"):
        matcher.search_show("Frieren", None)


def test_an_outage_falls_back_to_the_filename(tmp_path):
    class Down:
        def post(self, *args, **kwargs):
            raise OSError("network unreachable")

        get = post

    matcher = TvdbMatcher("key", cache=Cache(tmp_path / "c.sqlite"), session=Down())
    numbered = anime_item("[Judas] Shingeki no Kyojin - S04E01.mkv")
    counted = anime_item("[SubsPlease] Sousou no Frieren - 12.mkv")
    matcher.match_all([numbered, counted])
    assert matcher.unreachable
    assert numbered.confidence is Confidence.HIGH
    assert counted.confidence is Confidence.LOW
    assert "unreachable" in counted.note


def test_a_remembered_show_still_places_its_episodes(tmp_path, tvdb):
    from endslate.decisions import Decisions

    store = Decisions(tmp_path / "decisions.json")
    item = anime_item("[SubsPlease] Sousou no Frieren - 12 (1080p).mkv")
    store.remember(item, {"title": "Frieren: Beyond Journey's End", "year": 2023, "tvdb_id": 424536})
    fresh = anime_item("[SubsPlease] Sousou no Frieren - 12 (1080p).mkv")
    Resolver(None, store, tvdb=tvdb)([fresh])
    assert fresh.confidence is Confidence.HIGH
    assert fresh.parsed.season is not None and fresh.parsed.episode is not None
    assert fresh.meta.tvdb_id == 424536
