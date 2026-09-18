from pathlib import Path

import pytest

from endslate.junk import classify
from tests.fixtures.names import JUNK_NAMES, KEEP_NAMES


@pytest.mark.parametrize("name", JUNK_NAMES)
def test_junk_is_junk(name):
    kind, reason = classify(Path("/library/Movies/Thing") / name, 4096)
    assert kind == "junk", f"{name} classified as {kind}"
    assert reason


@pytest.mark.parametrize("name", KEEP_NAMES)
def test_keepers_are_kept(name):
    kind, _ = classify(Path("/library/Movies/Thing") / name, 4096)
    assert kind != "junk"


def test_large_video_named_sample_is_kept():
    kind, _ = classify(Path("/library/Movies/Sample People (2004)/Sample People.mkv"), 5_000_000_000)
    assert kind == "video"
