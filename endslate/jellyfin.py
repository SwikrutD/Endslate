"""Talk to Jellyfin, rather than guessing at it from the outside.

Renaming is the means. The end is that Jellyfin recognises everything, and only
Jellyfin can answer that. With an API key this module triggers the rescan after a
run and then asks which movies and shows it still could not identify, which is
the number that actually says whether the work succeeded.
"""
from __future__ import annotations

import os
import socket
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

TIMEOUT = 8.0
PORT_TIMEOUT = 1.0
PROCESS_NAMES = ("jellyfin", "jellyfin.exe", "jellyfin-server", "jellyfin-server.exe")
ID_KEYS = ("Tmdb", "Imdb", "Tvdb", "TmdbCollection", "Zap2It")
TOP_LEVEL_TYPES = ("Movie", "Series")
STALE_HINT = (
    "Jellyfin failing to drop an item it has lost is usually its own database refusing "
    "the delete. Look in its log for 'UNIQUE constraint failed: UserData'. See the README, "
    "under Jellyfin still shows the old names."
)


# --------------------------------------------------------------- is it running


def port_open(url: str = "http://localhost:8096") -> bool:
    parsed = urlparse(url if "://" in url else f"http://{url}")
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 8096)
    try:
        with socket.create_connection((host, port), timeout=PORT_TIMEOUT):
            return True
    except OSError:
        return False


def process_running() -> bool:
    import subprocess

    try:
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            output = subprocess.run(
                ["tasklist"], capture_output=True, text=True, timeout=8,
                creationflags=subprocess.CREATE_NO_WINDOW,
            ).stdout.lower()
        else:
            output = subprocess.run(
                ["ps", "-eo", "comm"], capture_output=True, text=True, timeout=8
            ).stdout.lower()
    except Exception:
        return False
    return any(name in output for name in PROCESS_NAMES)


def is_running(url: str = "http://localhost:8096") -> tuple[bool, str]:
    """Return (running, how we know)."""
    if port_open(url):
        return True, f"something is listening on {url}"
    if process_running():
        return True, "a Jellyfin process is running"
    return False, ""


# ------------------------------------------------------------------- the client


@dataclass
class LibraryReport:
    total: int = 0
    identified: int = 0
    unidentified: list[dict] = field(default_factory=list)
    stale: list[dict] = field(default_factory=list)
    stale_checked: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error

    @property
    def unidentified_count(self) -> int:
        return len(self.unidentified)

    @property
    def stale_count(self) -> int:
        return len(self.stale)

    def summary(self) -> str:
        if self.error:
            return self.error
        if not self.total:
            return "Jellyfin reported no movies or shows at all. Check the library paths."
        if not self.unidentified:
            text = f"Jellyfin identified all {self.total:,} movies and shows."
        else:
            text = (
                f"Jellyfin identified {self.identified:,} of {self.total:,}. "
                f"{self.unidentified_count:,} still have no provider id."
            )
        if self.stale:
            text += (
                f" {self.stale_count:,} of its entries point at files that no longer exist, "
                "so a rescan has not caught up with the rename."
            )
        return text

    def detail(self, limit: int = 200) -> str:
        """The lists behind the summary, for a read-only text box."""
        def rows(entries: list[dict]) -> list[str]:
            return [
                f"{row['type'] or 'item':7} {row['name']}\n        {row['path']}"
                for row in entries[:limit]
            ]

        lines: list[str] = []
        if self.stale:
            lines.append(f"STILL AT AN OLD PATH ({self.stale_count:,})")
            lines += rows(self.stale)
            lines += ["", STALE_HINT, ""]
        if self.unidentified:
            lines.append(f"NO PROVIDER ID ({self.unidentified_count:,})")
            lines += rows(self.unidentified)
        return "\n".join(lines).strip()


class JellyfinError(RuntimeError):
    pass


class JellyfinClient:
    def __init__(self, url: str, api_key: str = "", session=None):
        self.url = (url or "http://localhost:8096").rstrip("/")
        self.api_key = api_key.strip()
        self._session = session

    # ---------------------------------------------------------------- transport

    def _client(self):
        if self._session is None:
            import requests

            self._session = requests.Session()
        return self._session

    def _headers(self) -> dict:
        if not self.api_key:
            return {}
        return {
            "X-Emby-Token": self.api_key,
            "Authorization": f'MediaBrowser Token="{self.api_key}"',
        }

    def _request(self, method: str, path: str, **params):
        query = dict(params)
        if self.api_key:
            query.setdefault("api_key", self.api_key)
        return self._client().request(
            method,
            f"{self.url}{path}",
            params=query,
            headers=self._headers(),
            timeout=TIMEOUT,
        )

    # ------------------------------------------------------------------ calls

    def server_name(self) -> str:
        """Round-trip the key. Raises JellyfinError with something readable."""
        try:
            response = self._request("GET", "/System/Info")
        except Exception as exc:
            raise JellyfinError(f"Could not reach {self.url}: {exc}") from exc
        if response.status_code in (401, 403):
            raise JellyfinError("Jellyfin rejected that API key.")
        if response.status_code >= 400:
            raise JellyfinError(f"Jellyfin answered HTTP {response.status_code}.")
        data = response.json()
        return f"{data.get('ServerName', 'Jellyfin')} {data.get('Version', '')}".strip()

    def refresh(self) -> bool:
        """Ask Jellyfin to rescan. It answers immediately and works in the background."""
        try:
            response = self._request("POST", "/Library/Refresh")
        except Exception as exc:
            raise JellyfinError(f"Could not reach {self.url}: {exc}") from exc
        if response.status_code in (401, 403):
            raise JellyfinError("Jellyfin rejected that API key.")
        if response.status_code >= 400:
            raise JellyfinError(f"Jellyfin answered HTTP {response.status_code}.")
        return True

    def _first_user_id(self) -> Optional[str]:
        try:
            response = self._request("GET", "/Users")
            if response.status_code >= 400:
                return None
            users = response.json()
        except Exception:
            return None
        if not isinstance(users, list) or not users:
            return None
        for user in users:
            policy = user.get("Policy") or {}
            if policy.get("IsAdministrator"):
                return user.get("Id")
        return users[0].get("Id")

    def _items(self) -> list[dict]:
        params = {
            "recursive": "true",
            "includeItemTypes": "Movie,Series,Episode",
            "fields": "ProviderIds,Path",
            "enableImages": "false",
            "limit": 10000,
        }
        response = self._request("GET", "/Items", **params)
        if response.status_code >= 400:
            user_id = self._first_user_id()
            if user_id is None:
                raise JellyfinError(
                    f"Jellyfin answered HTTP {response.status_code} when asked for its items."
                )
            response = self._request("GET", f"/Users/{user_id}/Items", **params)
            if response.status_code >= 400:
                raise JellyfinError(
                    f"Jellyfin answered HTTP {response.status_code} when asked for its items."
                )
        payload = response.json()
        return payload.get("Items", []) if isinstance(payload, dict) else []

    def report(self) -> LibraryReport:
        """Which movies and shows Jellyfin could not put a provider id against."""
        out = LibraryReport()
        if not self.api_key:
            out.error = "Add a Jellyfin API key in Settings to ask it anything."
            return out
        try:
            items = self._items()
        except JellyfinError as exc:
            out.error = str(exc)
            return out
        except Exception as exc:
            out.error = f"Could not reach {self.url}: {exc}"
            return out

        _find_stale(items, out)
        for item in items:
            if (item.get("Type") or "Movie") not in TOP_LEVEL_TYPES:
                continue
            out.total += 1
            provider = item.get("ProviderIds") or {}
            if any(provider.get(key) for key in ID_KEYS):
                out.identified += 1
            else:
                out.unidentified.append(
                    {
                        "name": item.get("Name") or "(no name)",
                        "type": item.get("Type") or "",
                        "path": item.get("Path") or "",
                    }
                )
        return out


def _local_path(path: str) -> Optional[str]:
    """A path worth checking from here, or None when it cannot mean anything locally."""
    if not path or not os.path.isabs(path):
        return None
    anchor = os.path.splitdrive(path)[0] or os.path.sep
    return path if os.path.exists(anchor) else None


def _find_stale(items: list[dict], out: LibraryReport) -> None:
    """Items whose file is gone: a rename Jellyfin has not let go of.

    Only trusted when some of Jellyfin's paths do exist from here. If none do,
    Jellyfin is on another machine or sees the library under another name, and
    every item would look missing.
    """
    missing: list[dict] = []
    present = 0
    for item in items:
        if (item.get("Type") or "") not in ("Movie", "Episode"):
            continue
        path = _local_path(item.get("Path") or "")
        if path is None:
            continue
        if os.path.exists(path):
            present += 1
        else:
            missing.append(
                {
                    "name": item.get("Name") or "(no name)",
                    "type": item.get("Type") or "",
                    "path": path,
                }
            )
    if present:
        out.stale_checked = True
        out.stale = missing
