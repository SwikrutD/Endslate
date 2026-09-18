"""Deciding what is debris. Every rule here is conservative: when in doubt, keep."""
from __future__ import annotations

import re
from pathlib import Path

from endslate.parser import ARTWORK_EXTS, ARTWORK_NAMES, SUBTITLE_EXTS, VIDEO_EXTS

WEB_ASSET_EXTS = {".js", ".css", ".html", ".htm", ".m3u8", ".php", ".map", ".woff", ".woff2", ".ico"}

_AD_PATTERNS = [
    re.compile(r"^www\.", re.I),
    re.compile(r"yts", re.I),
    re.compile(r"yify", re.I),
    re.compile(r"\brarbg\b", re.I),
    re.compile(r"torrent\s*downloaded", re.I),
    re.compile(r"downloaded\s*from", re.I),
    re.compile(r"ahashare", re.I),
    re.compile(r"extratorrent", re.I),
    re.compile(r"demonoid", re.I),
    re.compile(r"\.com\b|\.net\b|\.mx\b|\.am\b|\.re\b|\.to\b", re.I),
    re.compile(r"proxies", re.I),
    re.compile(r"visit\s", re.I),
]

_AD_EXTS = {".txt", ".jpg", ".jpeg", ".png", ".url", ".html", ".nfo"}

SAMPLE_MAX_BYTES = 150 * 1024 * 1024


def is_apple_double(name: str) -> bool:
    return name.startswith("._") or name == ".DS_Store" or name == ".AppleDouble"


def is_os_cruft(name: str) -> bool:
    return name.lower() in {"thumbs.db", "desktop.ini", ".directory", "ehthumbs.db"}


def is_artwork(path: Path) -> bool:
    return path.suffix.lower() in ARTWORK_EXTS and path.stem.lower() in ARTWORK_NAMES


def is_advert(path: Path) -> bool:
    if path.suffix.lower() not in _AD_EXTS:
        return False
    if is_artwork(path):
        return False
    name = path.name
    return any(p.search(name) for p in _AD_PATTERNS)


def classify(path: Path, size: int) -> tuple[str, str]:
    """Return (kind, reason) where kind is one of the FileKind values."""
    name = path.name
    suffix = path.suffix.lower()

    if is_apple_double(name):
        return "junk", "macOS resource fork"
    if is_os_cruft(name):
        return "junk", "OS cruft"
    if suffix in WEB_ASSET_EXTS:
        return "junk", "web asset"
    if is_advert(path):
        return "junk", "release-site advert"
    if suffix in VIDEO_EXTS:
        if size <= SAMPLE_MAX_BYTES and re.search(r"(?<![A-Za-z0-9])sample(?![A-Za-z0-9])", name, re.I):
            return "junk", "sample clip"
        return "video", ""
    if suffix in SUBTITLE_EXTS:
        return "subtitle", ""
    if is_artwork(path):
        return "artwork", ""
    if suffix in ARTWORK_EXTS:
        return "other", "image, not recognised artwork"
    return "other", ""
