import pytest

from endslate.parser import parse
from endslate.subtitles import detect_language
from endslate.models import ScannedFile, FileKind
from pathlib import Path

from tests.fixtures.names import ANIME_NAMES, EPISODE_NAMES, MOVIE_NAMES, SUBTITLE_NAMES


@pytest.mark.parametrize("name,is_dir,expected", MOVIE_NAMES + EPISODE_NAMES + ANIME_NAMES)
def test_parse(name, is_dir, expected):
    parsed = parse(name, is_dir=is_dir)
    for field, value in expected.items():
        assert getattr(parsed, field) == value, f"{field} of {name!r}"


@pytest.mark.parametrize("name,code", SUBTITLE_NAMES)
def test_subtitle_language(name, code):
    sub = ScannedFile(path=Path("/library/Movies/X") / name, size=1, kind=FileKind.SUBTITLE)
    assert detect_language(sub) == code


def test_year_is_not_stolen_from_a_numeric_title():
    assert parse("2012.2009.1080p.BluRay.x264.mkv").title == "2012"
    assert parse("2012.2009.1080p.BluRay.x264.mkv").year == 2009


def test_sample_detection():
    assert parse("Some.Movie.2019.sample.mkv").is_sample
    assert not parse("Sampling.Time.2019.mkv").is_sample


def test_anime_context_reads_a_bare_episode_count():
    assert parse("Naruto Shippuden 001.mkv", anime=True).absolute == 1
    assert parse("Frieren E12.mkv", anime=True).absolute == 12
    # A number that is part of the title is not a count.
    assert parse("Mob Psycho 100.mkv", anime=True).absolute is None
    assert parse("Naruto Shippuden 001.mkv").absolute is None


def test_a_two_episode_file_keeps_both_numbers():
    parsed = parse("Dark.S01E01E02.1080p.mkv")
    assert (parsed.season, parsed.episode, parsed.episode_end) == (1, 1, 2)
