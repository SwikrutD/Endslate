"""A small stroke icon set, drawn as SVG and tinted to whatever colour is asked for.

Keeping the icons as source rather than image files means they follow the theme,
stay crisp on any display scaling, and add nothing to the repo but this file.
"""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_VIEW = 24
_STROKE = 1.7

_PATHS: dict[str, str] = {
    "library": "M3.5 8A1.5 1.5 0 0 1 5 6.5h3.6l1.6 2H19A1.5 1.5 0 0 1 20.5 10v8A1.5 1.5 0 0 1 19 19.5H5"
               "A1.5 1.5 0 0 1 3.5 18z",
    "review": "M4 7.5h8 M4 12.5h8 M4 17.5h5 M14.5 16.2l2.2 2.3 4.3-4.8",
    "apply": "M12 3.6a8.4 8.4 0 1 1-8.4 8.4A8.4 8.4 0 0 1 12 3.6z M8.6 12.1l2.4 2.4 4.6-5",
    "history": "M4.6 8.2A8.4 8.4 0 1 1 3.6 12 M3.6 4.4v4h4 M12 7.8V12l3.1 1.9",
    "settings": "M4 7.5h4 M13 7.5h7 M4 12.5h7 M16 12.5h4 M4 17.5h4 M13 17.5h7"
                " M10.5 5.6a1.9 1.9 0 1 1 0 3.8 1.9 1.9 0 0 1 0-3.8z"
                " M13.5 10.6a1.9 1.9 0 1 1 0 3.8 1.9 1.9 0 0 1 0-3.8z"
                " M10.5 15.6a1.9 1.9 0 1 1 0 3.8 1.9 1.9 0 0 1 0-3.8z",
    "search": "M10.8 4.6a6.2 6.2 0 1 1 0 12.4 6.2 6.2 0 0 1 0-12.4z M15.4 15.4l4.1 4.1",
    "arrow-right": "M4.5 12h14 M13 6.5l5.5 5.5-5.5 5.5",
    "chevron-right": "M9.5 5.5l6.5 6.5-6.5 6.5",
    "chevron-down": "M5.5 9.5l6.5 6.5 6.5-6.5",
    "check": "M5 12.6l4.6 4.6L19.2 6.8",
    "close": "M6.5 6.5l11 11 M17.5 6.5l-11 11",
    "folder": "M3.5 8A1.5 1.5 0 0 1 5 6.5h3.6l1.6 2H19A1.5 1.5 0 0 1 20.5 10v8A1.5 1.5 0 0 1 19 19.5H5"
              "A1.5 1.5 0 0 1 3.5 18z",
    "folder-open": "M3.5 18V7A1.5 1.5 0 0 1 5 5.5h3.4l1.6 2H17A1.5 1.5 0 0 1 18.5 9v1.5"
                   " M3.5 18l2.2-6.1A1.5 1.5 0 0 1 7.1 10.9H21l-2.3 6.4A1.5 1.5 0 0 1 17.3 18.3H5"
                   "A1.5 1.5 0 0 1 3.5 18z",
    "copy": "M9.5 9.5h9A1.5 1.5 0 0 1 20 11v8.5A1.5 1.5 0 0 1 18.5 21h-9A1.5 1.5 0 0 1 8 19.5V11"
            "A1.5 1.5 0 0 1 9.5 9.5z M5.5 15A1.5 1.5 0 0 1 4 13.5V5A1.5 1.5 0 0 1 5.5 3.5h9A1.5 1.5 0 0 1 16 5v1",
    "undo": "M8.6 8.6H4.2V4.2 M4.8 8.9A8.2 8.2 0 1 1 3.8 12.8",
    "refresh": "M15.4 8.6h4.4V4.2 M19.2 8.9A8.2 8.2 0 1 0 20.2 12.8",
    "warning": "M12 4.4l8.6 15.2H3.4z M12 10v4.2 M12 16.9v.7",
    "info": "M12 3.6a8.4 8.4 0 1 1 0 16.8 8.4 8.4 0 0 1 0-16.8z M12 11.2v5.4 M12 7.4v.8",
    "sparkle": "M12 3.6l2 5.7 5.7 2-5.7 2-2 5.7-2-5.7-5.7-2 5.7-2z",
    "sun": "M12 8.2a3.8 3.8 0 1 1 0 7.6 3.8 3.8 0 0 1 0-7.6z M12 3.4v1.8 M12 18.8v1.8"
           " M3.4 12h1.8 M18.8 12h1.8 M6 6l1.3 1.3 M16.7 16.7L18 18 M18 6l-1.3 1.3 M7.3 16.7L6 18",
    "moon": "M20.2 14.8A8.6 8.6 0 0 1 9.2 3.8 8.6 8.6 0 1 0 20.2 14.8z",
    "monitor": "M4.5 5.5h15a1 1 0 0 1 1 1v8.5a1 1 0 0 1-1 1h-15a1 1 0 0 1-1-1V6.5a1 1 0 0 1 1-1z"
               " M9 19.5h6 M12 16v3.5",
    "film": "M4.5 5.5h15v13h-15z M8.5 5.5v13 M15.5 5.5v13 M4.5 12h15",
    "trash": "M4.8 7h14.4 M9.6 7V4.8h4.8V7 M6.8 7l.9 12.2h8.6L17.2 7 M10.2 10.4v5.4 M13.8 10.4v5.4",
    "external": "M14.5 4.5h5v5 M19.5 4.5l-7.5 7.5"
                " M18 14v4.5A1.5 1.5 0 0 1 16.5 20h-11A1.5 1.5 0 0 1 4 18.5v-11A1.5 1.5 0 0 1 5.5 6H10",
    "filter": "M4 6.5h16 M7 12h10 M10 17.5h4",
    "key": "M14.6 4.6a4.6 4.6 0 1 1 0 9.2 4.6 4.6 0 0 1 0-9.2z M11.3 12.4L4 19.7v1.8h2.6v-2h2v-2h2l1.4-1.4",
    "play": "M8.5 5.4l10.5 6.6-10.5 6.6z",
    "dot": "M12 8.6a3.4 3.4 0 1 1 0 6.8 3.4 3.4 0 0 1 0-6.8z",
    "eye": "M12 6.2c4.4 0 7.6 3 8.8 5.8-1.2 2.8-4.4 5.8-8.8 5.8S4.4 14.8 3.2 12C4.4 9.2 7.6 6.2 12 6.2z"
           " M12 9.4a2.6 2.6 0 1 1 0 5.2 2.6 2.6 0 0 1 0-5.2z",
}

_FILLED = {"play", "dot", "sparkle"}


def _svg(name: str, colour: str) -> bytes:
    path = _PATHS[name]
    if name in _FILLED:
        body = f'<path d="{path}" fill="{colour}"/>'
    else:
        body = (
            f'<path d="{path}" fill="none" stroke="{colour}" stroke-width="{_STROKE}" '
            'stroke-linecap="round" stroke-linejoin="round"/>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_VIEW} {_VIEW}">{body}</svg>'
    ).encode("utf-8")


@lru_cache(maxsize=512)
def pixmap(name: str, colour: str, size: int = 18, ratio: float = 2.0) -> QPixmap:
    """A tinted icon at `size` logical pixels, rendered at `ratio` for sharpness.

    The pixmap carries its device pixel ratio, so the painter works in logical
    coordinates: render into size x size, not size*ratio.
    """
    if name not in _PATHS:
        name = "dot"
    renderer = QSvgRenderer(QByteArray(_svg(name, colour)))
    pm = QPixmap(int(round(size * ratio)), int(round(size * ratio)))
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pm


@lru_cache(maxsize=512)
def icon(name: str, colour: str, size: int = 18) -> QIcon:
    return QIcon(pixmap(name, colour, size))


def names() -> list[str]:
    return sorted(_PATHS)
