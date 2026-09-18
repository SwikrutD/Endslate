"""Notice when Jellyfin is running, so a run does not fight a library scan."""
from __future__ import annotations

import socket
from urllib.parse import urlparse

TIMEOUT = 1.0
PROCESS_NAMES = ("jellyfin", "jellyfin.exe", "jellyfin-server", "jellyfin-server.exe")


def port_open(url: str = "http://localhost:8096") -> bool:
    parsed = urlparse(url if "://" in url else f"http://{url}")
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 8096)
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT):
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
