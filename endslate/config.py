"""User settings and where they live. Never inside the media library."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

APP_NAME = "Endslate"


def app_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    directory = base / APP_NAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def config_path() -> Path:
    return app_dir() / "config.json"


def cache_path() -> Path:
    return app_dir() / "metadata-cache.sqlite"


def runs_dir() -> Path:
    directory = app_dir() / "runs"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


@dataclass
class Config:
    tmdb_api_key: str = ""
    metadata_language: str = "en-US"
    subtitle_language: str = "en"
    preset: str = "Jellyfin"
    last_root: str = ""
    english_only_subtitles: bool = True
    quarantine_junk: bool = True
    rename_top_level_folders: bool = True
    folder_per_movie: Optional[bool] = None
    check_jellyfin: bool = True
    jellyfin_url: str = "http://localhost:8096"
    fuzzy_threshold: float = 0.85
    custom_presets: list = field(default_factory=list)
    theme: str = "system"
    window_geometry: str = ""
    window_state: str = ""

    def save(self) -> None:
        config_path().write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


def load_config() -> Config:
    path = config_path()
    if not path.exists():
        return Config()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Config()
    known = set(Config.__dataclass_fields__)
    return Config(**{k: v for k, v in data.items() if k in known})
