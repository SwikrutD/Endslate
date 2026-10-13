"""Naming presets and the template renderer.

A preset is four template strings plus the two top-level folder names. Rendering
is deliberately forgiving: a token with no value collapses to nothing and the
surrounding whitespace is tidied afterwards, so one template covers both
'Fight Club (1999)' and 'Rush Hour' when the year is unknown.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Optional

TOKEN_RE = re.compile(r"\{(?P<name>[a-z_]+)(?::(?P<spec>[^}]+))?\}")

TOKEN_HELP = {
    "title": "Canonical title, e.g. Fight Club",
    "year": "Release year as digits, e.g. 1999",
    "year_paren": "Year in parentheses, or nothing when unknown",
    "season": "Season number, use {season:02} for 01",
    "episode": "Episode number, use {episode:02} for 04",
    "episode_title": "Episode name, or nothing",
    "episode_title_suffix": "Episode name preceded by a space",
    "episode_title_dash": "Episode name preceded by ' - '",
    "edition": "Directors Cut, IMAX, Unrated and similar",
    "edition_suffix": "Edition preceded by ' - '",
    "part": "Part or cut marker, e.g. A or 2",
    "part_suffix": "Part preceded by ' - '",
    "resolution": "1080p, 2160p and similar",
    "source": "BluRay, WEB-DL and similar",
    "episode_range": "-E02 when one file holds two episodes, or nothing",
    "episode_range_lower": "The same in lower case, -e02",
    "absolute": "Absolute episode number, as anime counts them",
    "tmdb_id": "Numeric TMDB id",
    "imdb_id": "tt0137523 style id",
    "tvdb_id": "Numeric TheTVDB id",
    "tvdb_tag": "[tvdbid-424536], which Jellyfin reads as the show's id",
    "tvdb_plex": "{tvdb-424536}, the same for Plex",
    "lang": "Subtitle language code",
    "ext": "File extension without the dot",
}


@dataclass
class Preset:
    name: str
    description: str
    movies_dir: str = "Movies"
    shows_dir: str = "Shows"
    movie_folder: str = "{title} {year_paren}"
    movie_file: str = "{title} {year_paren}{part_suffix}"
    season_folder: str = "Season {season:02}"
    episode_file: str = "{title} {year_paren} S{season:02}E{episode:02}{episode_range}{episode_title_suffix}"
    anime_dir: str = "Anime"
    # The show's TheTVDB id in its folder name pins it for Jellyfin, which
    # otherwise has a hard time telling one anime from its own sequel.
    anime_folder: str = "{title} {year_paren} {tvdb_tag}"
    folder_per_movie: bool = True
    builtin: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Preset":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


BUILTIN_PRESETS: list[Preset] = [
    Preset(
        name="Jellyfin",
        description="Jellyfin's documented layout. Folder per movie, Season 01 subfolders.",
    ),
    Preset(
        name="Plex",
        description="Plex's documented layout. Dashes between the show, the episode code and the title.",
        episode_file="{title} {year_paren} - s{season:02}e{episode:02}{episode_range_lower}{episode_title_dash}",
        anime_folder="{title} {year_paren} {tvdb_plex}",
    ),
    Preset(
        name="Flat",
        description="Movies as bare files with no folder. Shows keep season folders.",
        folder_per_movie=False,
    ),
    Preset(
        name="Kodi",
        description="Like Jellyfin but episode files carry no episode title.",
        episode_file="{title} {year_paren} S{season:02}E{episode:02}{episode_range}",
        anime_folder="{title} {year_paren}",
    ),
]


def builtin(name: str) -> Preset:
    for preset in BUILTIN_PRESETS:
        if preset.name.lower() == name.lower():
            return Preset(**asdict(preset))
    raise KeyError(name)


def _fmt(value, spec: Optional[str]) -> str:
    if value is None or value == "":
        return ""
    if spec:
        try:
            return format(value, spec)
        except (ValueError, TypeError):
            return str(value)
    return str(value)


def build_tokens(
    *,
    title: str = "",
    year: Optional[int] = None,
    season: Optional[int] = None,
    episode: Optional[int] = None,
    episode_end: Optional[int] = None,
    absolute: Optional[int] = None,
    episode_title: str = "",
    edition: str = "",
    part: str = "",
    resolution: str = "",
    source: str = "",
    tmdb_id: Optional[int] = None,
    imdb_id: str = "",
    tvdb_id: Optional[int] = None,
    lang: str = "",
    ext: str = "",
) -> dict:
    # A file holding S01E01 and S01E02 kept only the first number, so the
    # second episode vanished from the media server.
    has_range = episode_end is not None and episode is not None and episode_end > episode
    return {
        "title": title,
        "year": year,
        "year_paren": f"({year})" if year else "",
        "season": season,
        "episode": episode,
        "episode_range": f"-E{episode_end:02}" if has_range else "",
        "episode_range_lower": f"-e{episode_end:02}" if has_range else "",
        "absolute": absolute,
        "episode_title": episode_title,
        "episode_title_suffix": f" {episode_title}" if episode_title else "",
        "episode_title_dash": f" - {episode_title}" if episode_title else "",
        "edition": edition,
        "edition_suffix": f" - {edition}" if edition else "",
        "part": part,
        "part_suffix": f" - {part}" if part else "",
        "resolution": resolution,
        "source": source,
        "tmdb_id": tmdb_id,
        "imdb_id": imdb_id,
        "tvdb_id": tvdb_id,
        "tvdb_tag": f"[tvdbid-{tvdb_id}]" if tvdb_id else "",
        "tvdb_plex": f"{{tvdb-{tvdb_id}}}" if tvdb_id else "",
        "lang": lang,
        "ext": ext,
    }


def render(template: str, tokens: dict) -> str:
    def sub(match: re.Match) -> str:
        return _fmt(tokens.get(match.group("name")), match.group("spec"))

    out = TOKEN_RE.sub(sub, template)
    out = re.sub(r"\(\s*\)|\[\s*\]", "", out)
    out = re.sub(r"\s+", " ", out)
    out = re.sub(r"\s+([,)\]])", r"\1", out)
    out = re.sub(r"(?:\s-)+\s*$", "", out)
    return out.strip(" -")
