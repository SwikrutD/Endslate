import pytest

from endslate.parser import parse
from endslate.subtitles import detect_language
from endslate.models import ScannedFile, FileKind
from pathlib import Path

from tests.fixtures.names import EPISODE_NAMES, MOVIE_NAMES, SUBTITLE_NAMES


@pytest.mark.parametrize("name,is_dir,expected", MOVIE_NAMES + EPISODE_NAMES)
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
