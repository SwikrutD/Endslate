import hashlib
from pathlib import Path

import pytest

# The seven folder shapes found in the real library, reproduced with empty files.
SHAPES = {
    "Movies/American Psycho 2000 2160p BluRay x265-SWTYBLZ-4kHdHub.com.mkv": 1000,
    "Movies/Fight Club/Fight.Club.1999.REMASTERED.1080p.BluRay.DDP5.1.x265-GalaxyRG265.mkv": 2000,
    "Movies/Baby Driver/Baby Driver 2017.mp4": 2000,
    "Movies/Baby Driver/Baby Driver 2017.srt": 10,
    "Movies/Dune - Part One (2021) 1080p BluRay x265/Dune - Part One (2021) 1080p BluRay x265/Dune - Part One (2021) 1080p BluRay x265.mkv": 3000,
    "Movies/The Hangover/The Hangover (2009) [1080p] [BluRay] [YTS.MX]/The.Hangover.2009.1080p.BluRay.x264-[YTS.MX].mp4": 1500,
    "Movies/The Hangover/The Hangover (2009) [1080p] [BluRay] [YTS.MX]/www.YTS.MX.jpg": 5,
    "Movies/The Hangover/The Hangover Part II (2011) [1080p] [BluRay] [YTS.MX]/The.Hangover.Part.II.2011.1080p.BluRay.x264-[YTS.MX].mp4": 1500,
    "Movies/Bad Boys Ride Or Die (2024) [1080p] [WEBRip] [YTS.MX]/Bad.Boys.Ride.Or.Die.2024.1080p.WEBRip.x264-[YTS.MX].mp4": 1800,
    "Movies/Bad Boys Ride Or Die (2024) [1080p] [WEBRip] [YTS.MX]/Subs/English.srt": 10,
    "Movies/Bad Boys Ride Or Die (2024) [1080p] [WEBRip] [YTS.MX]/Subs/dan.srt": 10,
    "Movies/Bad Boys Ride Or Die (2024) [1080p] [WEBRip] [YTS.MX]/Subs/Latin American.spa.srt": 10,
    "Movies/Black Panther/Black Panther 2018 1080p.mp4": 1200,
    "Movies/Black Panther/._Black Panther 2018 1080p.mp4": 4,
    "Movies/Housefull 5/Housefull 5A (2025) Bollywood Hindi Movie PreDvD 1080p.mkv": 900,
    "Movies/Housefull 5/Housefull 5B (2025) Bollywood Hindi Movie PreDvD 720p.mkv": 900,
    "Movies/jquery.min/jquery.min/jquery.min.js": 3,
    "Movies/Rush Hour/Rush Hour.mkv": 1100,
    "Movies/Real Steel (2011)/Real Steel (2011).avi": 1000,
    "TV Shows/The 100/The.100.S01.1080p.AMZN.WEB-DL-4kHdHub.Com/The.100.S01E01.Pilot.1080p.AMZN.WEB-DL-4kHdHub.Com.mkv": 700,
    "TV Shows/The 100/The.100.S01.1080p.AMZN.WEB-DL-4kHdHub.Com/The.100.S01E02.Earth.Skills.1080p.AMZN.WEB-DL-4kHdHub.Com.mkv": 700,
    "TV Shows/Dark/Dark.S01.1080p.NF.WEB-DL-4kHdHub.Com/Dark.S01E01.Secrets.1080p.NF.WEB-DL-4kHdHub.Com.mkv": 700,
    "TV Shows/Dark/Dark.S01.1080p.NF.WEB-DL-4kHdHub.Com/Dark - season 1.en/Dark - 1x01 - Geheimnisse.WEB.STRiFE.en.srt": 10,
    "TV Shows/Squid Game/Season 3/Squid.Game.S03E01.Keys.and.Knives.1080p.NF.WEB-DL.AV1-4kHdHub.Com.mkv": 700,
    "TV Shows/Modern Family/Season 1/Modern Family (2009) - S01E01 - Pilot (1080p BluRay x265 Silence).mkv": 700,
    "TV Shows/Modern Family/Season 1/desktop.ini": 2,
    "TV Shows/Modern Family/New Folder/.keep": 0,
}


def _write(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    seed = hashlib.sha1(path.name.encode("utf-8")).digest()
    payload = (seed * ((size // len(seed)) + 1))[:size]
    path.write_bytes(payload)


@pytest.fixture
def library(tmp_path) -> Path:
    root = tmp_path / "Media"
    for relative, size in SHAPES.items():
        _write(root / relative, size)
    (root / "TV Shows" / "Modern Family" / "New Folder" / ".keep").unlink()
    return root


def snapshot(root: Path) -> dict[str, str]:
    out = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[str(path.relative_to(root))] = hashlib.sha1(path.read_bytes()).hexdigest()
    return out
