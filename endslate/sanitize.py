"""Turn an arbitrary title into something Windows and Jellyfin both accept."""
from __future__ import annotations

import re
import unicodedata

ILLEGAL = r'<>:"/\\|?*'
_ILLEGAL_RE = re.compile("[" + re.escape(ILLEGAL) + "]")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_WS_RE = re.compile(r"\s+")

RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

# Characters that read badly in a filename but have a safe stand-in.
REPLACEMENTS = {
    ":": " -",
    "/": " ",
    "\\": " ",
    "|": " ",
    "*": "",
    "?": "",
    '"': "'",
    "<": "(",
    ">": ")",
}

MAX_PATH = 260
MAX_COMPONENT = 200


def sanitize_component(name: str, *, allow_unicode: bool = True) -> str:
    """Make one path component legal on Windows without mangling the title."""
    if not name:
        return "Untitled"

    out = unicodedata.normalize("NFC", name)
    out = _CONTROL_RE.sub("", out)
    for bad, good in REPLACEMENTS.items():
        out = out.replace(bad, good)
    out = _ILLEGAL_RE.sub("", out)
    if not allow_unicode:
        out = out.encode("ascii", "ignore").decode("ascii")
    out = _WS_RE.sub(" ", out).strip()
    # Windows silently drops trailing dots and spaces, which breaks round-tripping.
    out = out.rstrip(". ")
    if not out:
        return "Untitled"
    if out.upper().split(".")[0] in RESERVED:
        out = out + "_"
    if len(out) > MAX_COMPONENT:
        out = out[:MAX_COMPONENT].rstrip(". ")
    return out


def path_too_long(path: str) -> bool:
    return len(str(path)) >= MAX_PATH


def shorten_to_fit(directory: str, stem: str, suffix: str) -> str:
    """Trim a stem so directory + stem + suffix stays under the path limit."""
    budget = MAX_PATH - len(directory) - len(suffix) - 2
    if budget < 8:
        return stem[:8]
    if len(stem) <= budget:
        return stem
    return stem[:budget].rstrip(". ")
