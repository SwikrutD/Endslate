"""Turn a messy release name into a best-effort guess.

Pure functions, no network, no filesystem. The title this produces is a search
key, not an answer: when a provider match exists its title wins.
"""
from __future__ import annotations

import re
from typing import Optional

from endslate.langs import MULTI, NOISE_TOKENS as LANG_NOISE, normalize as norm_lang
from endslate.models import ParsedName

VIDEO_EXTS = {".mkv", ".mp4", ".avi", ".m4v", ".mov", ".wmv", ".mpg", ".mpeg", ".ts", ".m2ts", ".flv", ".webm"}
SUBTITLE_EXTS = {".srt", ".ass", ".ssa", ".sub", ".idx", ".vtt", ".sup"}
ARTWORK_NAMES = {"poster", "folder", "fanart", "banner", "logo", "backdrop", "thumb", "clearart", "disc", "cover"}
ARTWORK_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tbn"}

RESOLUTIONS = {"2160p", "1080p", "720p", "480p", "576p", "1440p", "4k", "8k", "uhd", "fhd", "qhd", "hd", "sd"}

# Deliberately excludes "red", "sky", "max", "stan" and "cam". They are real
# streaming and capture tags, and they are also ordinary words that turn up in
# episode titles: Red Alert, Red Sky at Morning, Red Queen, Max Payne.
SOURCES = {
    "bluray", "blu", "brrip", "bdrip", "bdremux", "remux", "webrip", "webdl", "web", "hdrip",
    "dvdrip", "dvdscr", "dvd", "hdtv", "pdtv", "predvd", "hdcam", "camrip", "telesync",
    "amzn", "nf", "netflix", "itunes", "dsnp", "hmax", "atvp", "hulu", "pcok",
    "pmtp", "crav", "vmax", "uhdtv", "hdts",
}

CODECS = {
    "x264", "x265", "h264", "h265", "hevc", "avc", "av1", "xvid", "divx", "vp9", "mpeg2",
    "10bit", "8bit", "12bit", "hi10p", "hi10", "10bits",
}

HDR = {"hdr", "hdr10", "hdr10plus", "dv", "dovi", "sdr", "hlg"}

AUDIO = {
    "aac", "ac3", "eac3", "dd", "ddp", "dts", "dtshd", "truehd", "atmos", "flac", "mp3", "opus",
    "ma", "6ch", "2ch", "8ch", "lpcm", "pcm", "aac5", "ddp5", "dd5", "aac2", "ddp2", "dd2",
    "224kbps", "640kbps", "dtsx",
}

MISC = {
    "repack", "proper", "internal", "limited", "esub", "esubs", "msub", "msubs", "subs", "sub",
    "subbed", "dubbed", "dual", "org", "untouched", "ds4k", "hq", "web-dl",
    "bollywood", "hollywood", "www", "torrent", "downloaded", "predvdrip", "nfrip",
    "batch",
}

EDITIONS = [
    ("unrated dc", "Unrated Directors Cut"),
    ("unrated directors cut", "Unrated Directors Cut"),
    ("directors cut", "Directors Cut"),
    ("director's cut", "Directors Cut"),
    ("final cut", "Final Cut"),
    ("extended", "Extended"),
    ("unrated", "Unrated"),
    ("uncut", "Uncut"),
    ("remastered", "Remastered"),
    ("theatrical", "Theatrical"),
    ("special edition", "Special Edition"),
    ("ultimate edition", "Ultimate Edition"),
    ("imax", "IMAX"),
    ("criterion", "Criterion"),
    ("anniversary edition", "Anniversary Edition"),
]

# Tokens that are certainly noise regardless of position.
NOISE = RESOLUTIONS | SOURCES | CODECS | HDR | AUDIO | MISC | LANG_NOISE | MULTI

# Scene-group names collide with real words: GHOSTS, SILENCE and STRiFE are all
# release groups and all plausible episode titles. They end a title only when
# something technical has already appeared, so the episode-title pass ignores them.
HARD_NOISE = RESOLUTIONS | SOURCES | CODECS | HDR | AUDIO | MULTI | LANG_NOISE | {
    "repack", "proper", "esub", "esubs", "msub", "msubs", "web-dl", "www", "torrent",
}

# Release sites and scene groups appear as domains or as a trailing -GROUP.
_SITE_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:www\.)?[A-Za-z0-9][A-Za-z0-9\-]*\.(?:com|net|org|mx|am|re|to|co|io|me|info|xyz|site|pro)(?![A-Za-z])",
    re.I,
)
_KNOWN_GROUPS = {
    "yts", "yify", "rarbg", "galaxyrg", "galaxyrg265", "psa", "stoic", "lumix", "darq", "hone",
    "absinth", "silence", "strife", "mzabi", "ghosts", "swtyblz", "frds", "mnhd", "ralphy",
    "xtrem3x", "taoe", "4khdhub", "hdhub", "hollymoviehd", "mkvcage", "10xflix", "ettv", "ext",
    "extratorrent", "demonoid", "ahashare", "yifystatus", "ytsproxies", "anoxmous", "ctrlhd",
    "sparks", "fgt", "evo", "tigole", "qxr", "megusta", "minx", "successfulcrab", "edith",
    "playweb", "flux", "ntb", "kogi", "tepes", "cakes", "syncopy", "sartre", "ntg", "afg",
}

_SEP = r"[\s._\-\[\]()+,]"
_BOUND = r"(?<![A-Za-z0-9])"
_EBOUND = r"(?![A-Za-z0-9])"

_EPISODE_PATTERNS = [
    # S01E02, S01E02E03, S01E02-E03, s01.e02
    re.compile(r"(?<![A-Za-z0-9])s(?P<s>\d{1,2})[\s._\-]*e(?P<e>\d{1,3})(?:[\s._\-]*(?:e|-)(?P<e2>\d{1,3}))?(?![0-9])", re.I),
    # 1x02, 01x02
    re.compile(r"(?<![A-Za-z0-9])(?P<s>\d{1,2})x(?P<e>\d{1,3})(?![0-9])", re.I),
    # Season 1 Episode 2
    re.compile(r"season[\s._\-]*(?P<s>\d{1,2})[\s._\-]*episode[\s._\-]*(?P<e>\d{1,3})(?![0-9])", re.I),
]

_SEASON_ONLY_PATTERNS = [
    # "Mob Psycho 100 2nd Season - 03", the way anime releases name a sequel
    # season. First, or "Season - 03" reads as season three.
    re.compile(r"(?<![A-Za-z0-9])(?P<s>\d{1,2})(?:st|nd|rd|th)[\s._\-]+season(?![A-Za-z])", re.I),
    re.compile(r"(?<![A-Za-z0-9])s(?P<s>\d{1,2})(?![0-9eExX])", re.I),
    re.compile(r"(?<![A-Za-z])season(?:[\s._]+|-)?(?P<s>\d{1,2})(?![0-9])", re.I),
]

_EPISODE_ONLY_PATTERNS = [
    re.compile(r"(?<![A-Za-z0-9])e(?:p|pisode)?[\s._\-]*(?P<e>\d{1,3})(?![0-9])", re.I),
]

# Anime and fansub conventions. A release opens with its group in brackets and
# numbers episodes from the start of the show: "[SubsPlease] Frieren - 12".
_GROUP_RE = re.compile(r"^\s*[\[【](?P<g>[^\]】\[]{1,48})[\]】][\s._\-]*")
_CRC_RE = re.compile(r"[\[(](?P<crc>[0-9A-Fa-f]{8})[\])]")
_TVDBID_RE = re.compile(r"[\[{]\s*tvdb(?:id)?\s*[-=]\s*(?P<id>\d+)\s*[\]}]", re.I)
_BATCH_RANGE_RE = re.compile(r"[\[(]\s*\d{1,4}\s*[-~]\s*\d{1,4}\s*[\])]")
# " - 12", " - 1085", " - 01v2": the dash form every fansub group uses.
_ABS_DASH_RE = re.compile(r"\s[-–]\s+(?:#|ep?\.?\s?)?(?P<e>\d{1,4})(?:v\d)?(?=$|[\s\[(._])", re.I)
# "EP05", "Episode 12", or a bare "E12" where the context says anime.
_ABS_EP_RE = re.compile(r"(?<![A-Za-z0-9])(?P<word>ep|episode|e|#)[\s._\-]?(?P<e>\d{1,4})(?:v\d)?(?![0-9])", re.I)
# "Naruto Shippuden 001": a zero-padded number at the end is a count, not a sequel.
_ABS_TRAILING_RE = re.compile(r"(?<![A-Za-z0-9])(?P<e>0\d{1,3})(?:v\d)?\s*$")

_YEAR_BRACKETED = re.compile(r"[\[(](?P<y>19\d{2}|20\d{2})[\])]")
_YEAR_BARE = re.compile(r"(?<![A-Za-z0-9])(?P<y>19\d{2}|20\d{2})(?![A-Za-z0-9])")
_PART_RE = re.compile(r"(?<![A-Za-z0-9])(?:cd|disc|disk|part|pt)[\s._\-]*(?P<p>\d{1,2})(?![0-9])", re.I)
_TRAILING_CUT_RE = re.compile(r"^(?P<base>.*\d)\s*(?P<letter>[A-D])$")
# Endslate's own output for a multi-cut release: "Housefull 5 (2025) - A.mkv".
# Without this the part is lost on a rescan and the two cuts collide.
_OWN_PART_RE = re.compile(
    r"\)\s*-\s*(?P<part>[A-D]|(?:Part|Pt|CD|Disc)\s*\d{1,2})\s*$", re.I
)
_SAMPLE_RE = re.compile(r"(?<![A-Za-z0-9])sample(?![A-Za-z0-9])", re.I)

MAX_SANE_YEAR = 2100


def _token_noise_spans(text: str, *, hard_only: bool = False) -> list[tuple[int, int]]:
    """Spans of text that are certainly release noise."""
    vocabulary = HARD_NOISE if hard_only else NOISE
    spans: list[tuple[int, int]] = []
    for m in _SITE_RE.finditer(text):
        spans.append(m.span())
    for m in re.finditer(r"[A-Za-z0-9][A-Za-z0-9'+]*", text):
        tok = m.group(0).lower()
        if tok in vocabulary or (not hard_only and tok in _KNOWN_GROUPS):
            spans.append(m.span())
        elif re.fullmatch(r"\d+kbps|\d+mb|\d+gb", tok):
            spans.append(m.span())
    return sorted(spans)


def _normalize_separators(text: str) -> str:
    out = text.replace("_", " ")
    # Dot-separated names only: leave "Mr. and Mrs. Smith" alone.
    if out.count(".") > out.count(" "):
        out = out.replace(".", " ")
    out = re.sub(r"\s+", " ", out)
    return out.strip()


_OPENERS = {")": "(", "]": "[", "}": "{"}
_EDGE = " -_.+,&"


def _clean_title(text: str) -> str:
    """Trim separators from the edges without breaking a balanced bracket.

    "Dreamscaperers (1)" must keep its closing bracket. "Dune - Part One (" must
    lose its dangling one.
    """
    out = _normalize_separators(text)
    while out and out[0] in _EDGE + "([{":
        out = out[1:]
    changed = True
    while changed and out:
        changed = False
        while out and out[-1] in _EDGE:
            out, changed = out[:-1], True
        if out and out[-1] in _OPENERS:
            opener = _OPENERS[out[-1]]
            if out.count(opener) < out.count(out[-1]):
                out, changed = out[:-1], True
        if out and out[-1] in "([{":
            out, changed = out[:-1], True
    return re.sub(r"\s+", " ", out).strip()


def _titlecase_if_shouted(text: str) -> str:
    if len(text.split()) < 2:
        return text
    letters = [c for c in text if c.isalpha()]
    if letters and all(c.isupper() for c in letters) and len(letters) > 3:
        return " ".join(w.capitalize() if w.isupper() else w for w in text.split())
    return text


def detect_edition(text: str) -> str:
    low = _normalize_separators(text).lower()
    for needle, label in EDITIONS:
        if re.search(_BOUND + re.escape(needle) + _EBOUND, low):
            return label
    return ""


def detect_language(text: str) -> str:
    """Language implied by a subtitle-style name such as 'x.en.srt' or 'dan'."""
    normalized = _normalize_separators(text).lower()
    whole = norm_lang(normalized)
    if whole:
        return whole
    parts = [p for p in re.split(r"[\s._\-()\[\]]+", normalized) if p]
    # Short codes are ordinary words in titles: "no" in Sousou no Frieren and
    # Point of No Return read as Norwegian and the English subtitle went to
    # quarantine. A two-letter code counts only as the last word, a three-letter
    # one only in the last two, a full name anywhere but the start.
    position = 0
    for index in range(len(parts) - 1, -1, -1):
        tok = parts[index]
        if tok in ("forced", "sdh", "cc", "hi"):
            continue
        code = norm_lang(tok)
        if code and (
            (len(tok) == 2 and position == 0)
            or (len(tok) == 3 and position <= 1)
            or (len(tok) > 3 and index > 0)
        ):
            return code
        position += 1
    return ""


def parse_season_from_folder(name: str) -> Optional[int]:
    for pat in _SEASON_ONLY_PATTERNS:
        m = pat.search(name)
        if m:
            return int(m.group("s"))
    return None


def _strip_release_group(raw: str, out: ParsedName) -> str:
    """Take a leading "[Group]" off the name and remember it.

    Left in place it became the start of the title: "SubsPlease] Frieren - 12".
    A bracket that is the whole name, like "[REC] (2007)", is the title itself.
    """
    m = _GROUP_RE.match(raw)
    if not m:
        return raw
    group = m.group("g").strip()
    rest = raw[m.end():]
    if not _clean_title(_YEAR_BRACKETED.sub("", rest)):
        return raw
    if re.fullmatch(r"(?:19|20)\d{2}|\d{3,4}p", group, re.I):
        return raw
    out.release_group = group
    return rest


def parse(name: str, *, is_dir: bool = False, anime: bool = False) -> ParsedName:
    """Parse one file or folder name.

    `anime` says the name comes from somewhere anime lives, so a bare episode
    count ("Naruto 001", "E12") is read as one. Without it only the forms that
    cannot be anything else are: a leading [Group] or a zero-padded " - 01".
    """
    raw = name if is_dir else re.sub(r"\.[A-Za-z0-9]{1,5}$", "", name)
    out = ParsedName()
    out.is_sample = bool(_SAMPLE_RE.search(raw))

    tm = _TVDBID_RE.search(raw)
    if tm:
        out.tvdb_id = int(tm.group("id"))
        raw = (raw[:tm.start()] + " " + raw[tm.end():]).strip()
    raw = _strip_release_group(raw, out)
    crc = _CRC_RE.search(raw)
    if crc:
        raw = (raw[:crc.start()] + " " + raw[crc.end():]).rstrip()

    cuts: list[int] = []
    batch = _BATCH_RANGE_RE.search(raw)
    if batch:
        cuts.append(batch.start())

    # 1. Episode marker wins over everything else.
    ep_end = None
    for pat in _EPISODE_PATTERNS:
        m = pat.search(raw)
        if m:
            out.season = int(m.group("s"))
            out.episode = int(m.group("e"))
            if m.groupdict().get("e2"):
                out.episode_end = int(m.group("e2"))
            cuts.append(m.start())
            ep_end = m.end()
            break
    if out.season is None:
        m = None
        for pat in _SEASON_ONLY_PATTERNS:
            m = pat.search(raw)
            if m:
                out.season = int(m.group("s"))
                cuts.append(m.start())
                break
        if out.season is not None and out.episode is None:
            for pat in _EPISODE_ONLY_PATTERNS:
                m2 = pat.search(raw, m.end() if m else 0)
                if m2:
                    out.episode = int(m2.group("e"))
                    ep_end = m2.end()
                    break
        if out.season is not None and out.episode is None and not is_dir:
            # "Spy x Family S2 - 05", "Frieren 2nd Season - 03"
            m2 = _ABS_DASH_RE.search(raw, m.end() if m else 0)
            if m2:
                out.episode = int(m2.group("e"))
                ep_end = m2.end()

    # 1b. No season anywhere: an absolute episode number, as anime counts them.
    abs_span = None
    if out.season is None and not is_dir:
        fansub = anime or bool(out.release_group)
        for m3 in _ABS_DASH_RE.finditer(raw):
            if fansub or m3.group("e").startswith("0"):
                abs_span = m3
                break
        if abs_span is None:
            for m3 in _ABS_EP_RE.finditer(raw):
                if m3.group("word").lower() in ("ep", "episode") or fansub:
                    abs_span = m3
                    break
        if abs_span is None and anime:
            head = raw
            noise = _token_noise_spans(raw, hard_only=True)
            if noise:
                head = raw[:noise[0][0]]
            head = re.sub(r"[\s._\-\[(]+$", "", head)
            m3 = _ABS_TRAILING_RE.search(head)
            if m3 and m3.start() > 0:
                abs_span = m3
        if abs_span is not None:
            out.absolute = int(abs_span.group("e"))
            cuts.append(abs_span.start())
            ep_end = abs_span.end()

    # 2. Year: a bracketed one is a deliberate statement, a bare one is a guess.
    ym = _YEAR_BRACKETED.search(raw)
    if ym:
        out.year = int(ym.group("y"))
        cuts.append(ym.start())
    else:
        for ym in _YEAR_BARE.finditer(raw):
            value = int(ym.group("y"))
            # A year cannot be the whole title unless nothing else is there.
            if ym.start() == 0 and len(raw) > 6:
                continue
            # "One Piece - 1085" is an episode; so is "Show - 2001" in a fansub name.
            if abs_span is not None and abs_span.start() <= ym.start() < abs_span.end():
                continue
            out.year = value
            cuts.append(ym.start())
            break

    # 3. Release noise.
    noise = _token_noise_spans(raw)
    if noise:
        cuts.append(noise[0][0])

    # 4. Title is whatever comes before the earliest marker.
    cut = min(cuts) if cuts else len(raw)
    title = _clean_title(raw[:cut])
    if not title:
        title = _clean_title(raw)
    title = _titlecase_if_shouted(title)

    # "Housefull 5A" is cut A of Housefull 5, not a film called Housefull 5A.
    cm = _TRAILING_CUT_RE.match(title)
    if cm and len(title) > 3:
        out.part = cm.group("letter")
        title = cm.group("base").strip()

    out.title = title

    # 5. Episode title: between the episode marker and the first noise after it.
    if ep_end is not None:
        tail_start = ep_end
        tail_end = len(raw)
        for start, end in _token_noise_spans(raw, hard_only=True):
            if start >= tail_start:
                tail_end = start
                break
        candidate = _clean_title(raw[tail_start:tail_end])
        candidate = re.sub(r"^(?:e\d{1,3}|-|–)\s*", "", candidate, flags=re.I).strip(" -")
        if candidate:
            out.episode_title = _titlecase_if_shouted(candidate)

    # 6. Decorations.
    out.edition = detect_edition(raw)
    own = _OWN_PART_RE.search(raw)
    if own:
        out.part = own.group("part").strip()
    pm = _PART_RE.search(raw)
    if pm and not out.part:
        out.part = pm.group("p")
    for token in RESOLUTIONS:
        if re.search(_BOUND + re.escape(token) + _EBOUND, raw, re.I):
            out.resolution = token if token != "4k" else "2160p"
            break
    for token in ("bluray", "remux", "webrip", "webdl", "web", "hdtv", "dvdrip", "hdrip", "brrip", "bdrip", "predvd"):
        if re.search(_BOUND + re.escape(token) + _EBOUND, raw, re.I):
            out.source = {"webdl": "WEB-DL", "web": "WEB", "bluray": "BluRay"}.get(token, token.upper())
            break
    out.language = detect_language(raw) if not is_dir else ""
    # A bracketed group plus an episode number is a fansub release. A site
    # name in the brackets is a western scene release that borrowed the habit.
    out.anime_hint = bool(
        out.release_group
        and not _SITE_RE.search(out.release_group)
        and (out.has_episode_number or crc is not None)
    )
    return out


def merge(file_parse: ParsedName, folder_parse: ParsedName) -> ParsedName:
    """Combine a file's parse with its folder's, preferring whichever is richer."""
    out = ParsedName(**vars(file_parse))
    if not out.title or len(out.title) < 2:
        out.title = folder_parse.title
    if out.year is None:
        out.year = folder_parse.year
    if out.season is None:
        out.season = folder_parse.season
    if out.episode is None:
        out.episode = folder_parse.episode
    if not out.edition:
        out.edition = folder_parse.edition
    if not out.part:
        out.part = folder_parse.part
    if out.tvdb_id is None:
        out.tvdb_id = folder_parse.tvdb_id
    out.anime_hint = out.anime_hint or folder_parse.anime_hint
    # A folder title that carries a year is usually the more deliberate name.
    if folder_parse.year is not None and folder_parse.title and len(folder_parse.title) >= len(out.title):
        out.title = folder_parse.title
    return out
