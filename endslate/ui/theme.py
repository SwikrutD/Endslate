"""The design system: colour, type, spacing, and the stylesheet built from them.

Chalk on slate. An end slate is black and white, written on in chalk, and the
interface follows it: every control is a neutral, the primary action is chalk
(ink, in the light theme), and colour is kept for one job only, which is saying
what state a file is in. Green will move, amber needs you, red collides, violet
goes to quarantine. If something is coloured, it means something.

The one ornament is the clapstick stripe at the head of the rail and over the
commit card on Apply, the moment the slate is actually clapped.

Everything a widget needs comes from the tokens below, so the two themes stay
in step and nothing hard-codes a colour.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Mode = Literal["dark", "light"]

FONT_UI = '"Segoe UI Variable Text", "Segoe UI", Inter, "Noto Sans", sans-serif'
FONT_DISPLAY = '"Segoe UI Variable Display", "Segoe UI Variable Text", "Segoe UI", sans-serif'
FONT_MONO = '"Cascadia Mono", Consolas, "JetBrains Mono", "DejaVu Sans Mono", monospace'
MONO_FAMILIES = ["Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono", "monospace"]
DISPLAY_FAMILIES = ["Segoe UI Variable Display", "Segoe UI Variable Text", "Segoe UI"]

# Type scale, in points. Small steps, because this is a dense tool.
SIZE_DISPLAY = 25
SIZE_TITLE = 20
SIZE_SUBTITLE = 14
SIZE_BODY = 13
SIZE_SMALL = 12
SIZE_CAPTION = 11
SIZE_MICRO = 10

# Spacing scale. Every margin and gap in the app is one of these.
SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "2xl": 32, "3xl": 44}

# Tight corners. This is a tool that sits beside an editing suite, not an app store.
RADIUS_SM = 4
RADIUS_MD = 6
RADIUS_LG = 8

STRIPE_HEIGHT = 8
RAIL_WIDTH = 220
CONTENT_MAX = 1320


@dataclass(frozen=True)
class Palette:
    canvas: str
    rail: str
    surface: str
    surface_alt: str
    surface_hi: str
    line: str
    line_strong: str
    text: str
    text_dim: str
    text_faint: str
    accent: str
    accent_hover: str
    accent_press: str
    accent_soft: str
    accent_text: str
    on_accent: str
    green: str
    green_soft: str
    green_text: str
    amber: str
    amber_soft: str
    amber_text: str
    red: str
    red_soft: str
    red_text: str
    blue: str
    blue_soft: str
    blue_text: str
    selection: str
    shade: str


# Warm graphite rather than blue-black: the room a grade is done in, lit by a
# tungsten practical. Chalk is the accent. Status colours are pitched so each
# one reads on its own soft ground at 4.5:1 or better.
DARK = Palette(
    canvas="#121110",
    rail="#0C0B0A",
    surface="#191816",
    surface_alt="#201E1C",
    surface_hi="#2A2825",
    line="#2B2926",
    line_strong="#3F3C37",
    text="#F0ECE5",
    text_dim="#ADA79E",
    text_faint="#78726A",
    accent="#F0ECE5",
    accent_hover="#FFFFFF",
    accent_press="#D8D3CA",
    accent_soft="#2A2825",
    accent_text="#F0ECE5",
    on_accent="#121110",
    green="#5FB77C",
    green_soft="#162219",
    green_text="#93D8A8",
    amber="#E2AA47",
    amber_soft="#2A2115",
    amber_text="#F2CB7C",
    red="#E2625B",
    red_soft="#2D1817",
    red_text="#F59791",
    blue="#9A92F0",
    blue_soft="#1D1B2E",
    blue_text="#C2BCF8",
    selection="#26241F",
    shade="#000000",
)

# Chalk becomes ink on paper: a warm off-white, never a clinical grey-blue.
LIGHT = Palette(
    canvas="#F3F1EC",
    rail="#E9E6DF",
    surface="#FBFAF7",
    surface_alt="#F0EDE7",
    surface_hi="#E6E2DA",
    line="#E0DCD4",
    line_strong="#C9C3B8",
    text="#1A1917",
    text_dim="#57524B",
    text_faint="#8A847A",
    accent="#1A1917",
    accent_hover="#34322E",
    accent_press="#000000",
    accent_soft="#E6E2DA",
    accent_text="#1A1917",
    on_accent="#FBFAF7",
    green="#23794A",
    green_soft="#E5F1E8",
    green_text="#1A5E39",
    amber="#9B6A0C",
    amber_soft="#F8EDD6",
    amber_text="#744F08",
    red="#B8332D",
    red_soft="#F9E6E4",
    red_text="#932722",
    blue="#5B4FC4",
    blue_soft="#ECEAFA",
    blue_text="#443A9E",
    selection="#E9E5DD",
    shade="#8A847A",
)

PALETTES: dict[str, Palette] = {"dark": DARK, "light": LIGHT}

# Bucket to colour family, used by pills, dots and the filter tiles.
BUCKET_TONE = {
    "planned": "green",
    "needs_you": "amber",
    "duplicate": "red",
    "junk": "blue",
    "skipped": "neutral",
    "noop": "neutral",
}


def tone_colours(palette: Palette, tone: str) -> tuple[str, str, str]:
    """Return (strong, soft background, readable text) for a tone name."""
    if tone == "neutral":
        return palette.text_faint, palette.surface_alt, palette.text_dim
    return (
        getattr(palette, tone),
        getattr(palette, f"{tone}_soft"),
        getattr(palette, f"{tone}_text"),
    )


def detect_mode() -> Mode:
    """Follow Windows' app theme when we can read it, otherwise assume dark."""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if value else "dark"
    except Exception:
        pass
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            window = app.palette().window().color()
            return "light" if window.lightness() > 127 else "dark"
    except Exception:
        pass
    return "dark"


def resolve_mode(preference: str) -> Mode:
    if preference in ("dark", "light"):
        return preference  # type: ignore[return-value]
    return detect_mode()


# role: (points, weight, family). Counts are set in the mono face, like the
# timecode on a smart slate, so a column of numbers lines up digit for digit.
ROLE_FONT = {
    "display": (SIZE_DISPLAY, 600, "display"),
    "title": (SIZE_TITLE, 600, "display"),
    "section": (SIZE_MICRO, 700, "ui"),
    "subtitle": (SIZE_SUBTITLE, 400, "ui"),
    "body": (SIZE_BODY, 400, "ui"),
    "muted": (SIZE_SMALL, 400, "ui"),
    "caption": (SIZE_CAPTION, 400, "ui"),
    "mono": (SIZE_SMALL, 400, "mono"),
    "metric": (SIZE_DISPLAY, 400, "mono"),
    "danger": (SIZE_SMALL, 400, "ui"),
}


def mono_font(points: int = SIZE_SMALL, weight: int = 400):
    """The monospaced face with real fallbacks, for code painted by hand."""
    from PySide6.QtGui import QFont

    font = QFont()
    font.setFamilies(MONO_FAMILIES)
    font.setStyleHint(QFont.Monospace)
    font.setPointSize(points)
    font.setWeight(QFont.Weight(weight))
    return font


def apply_role_font(widget, role: str) -> None:
    """Set the font in code as well as QSS.

    Qt computes a widget's size hint before the stylesheet lands, so a label that
    only gets its size from QSS reserves the wrong height and collides with its
    neighbour. Setting the font here keeps every layout honest.
    """
    from PySide6.QtGui import QFont

    size, weight, family = ROLE_FONT.get(role, ROLE_FONT["body"])
    font = QFont(widget.font())
    if family == "mono":
        font.setFamilies(MONO_FAMILIES)
        font.setStyleHint(QFont.Monospace)
    elif family == "display":
        font.setFamilies(DISPLAY_FAMILIES)
    font.setPointSize(size)
    font.setWeight(QFont.Weight(weight))
    if role == "section":
        font.setLetterSpacing(QFont.PercentageSpacing, 118)
    elif family == "display":
        font.setLetterSpacing(QFont.PercentageSpacing, 98)
    widget.setFont(font)


def _checkbox_images(mode: Mode) -> tuple[str, str]:
    """QSS cannot draw a tick, so write one out and point at it."""
    from endslate.config import app_dir
    from endslate.ui import icons

    palette = PALETTES[mode]
    folder = app_dir() / "style"
    folder.mkdir(parents=True, exist_ok=True)
    check = folder / f"check-{mode}.png"
    dash = folder / f"dash-{mode}.png"
    try:
        icons.pixmap("check", palette.on_accent, 12).save(str(check))
        icons.pixmap("arrow-right", palette.accent, 12).save(str(dash))
    except Exception:
        return "", ""
    return check.as_posix(), dash.as_posix()


def stylesheet(mode: Mode, check_url: str = "", dash_url: str = "") -> str:
    p = PALETTES[mode]
    s = SPACE
    check_rule = f"image: url({check_url});" if check_url else ""
    dash_rule = f"image: url({dash_url});" if dash_url else ""
    field_bg = p.canvas if mode == "dark" else p.surface
    return f"""
/* ---------------------------------------------------------------- base */
QWidget {{
    background: transparent;
    color: {p.text};
    font-family: {FONT_UI};
    font-size: {SIZE_BODY}pt;
}}
QMainWindow, QDialog {{ background: {p.canvas}; }}
QStatusBar {{ background: {p.canvas}; color: {p.text_faint}; border: none; }}
QToolTip {{
    background: {p.surface_hi};
    color: {p.text};
    border: 1px solid {p.line_strong};
    border-radius: {RADIUS_SM}px;
    padding: 6px 9px;
    font-size: {SIZE_SMALL}pt;
}}

/* --------------------------------------------------------- typography */
QLabel[role="display"] {{ font-family: {FONT_DISPLAY}; font-size: {SIZE_DISPLAY}pt; font-weight: 600; color: {p.text}; }}
QLabel[role="title"]   {{ font-family: {FONT_DISPLAY}; font-size: {SIZE_TITLE}pt; font-weight: 600; color: {p.text}; }}
QLabel[role="section"] {{
    font-size: {SIZE_MICRO}pt; font-weight: 700; color: {p.text_faint};
    letter-spacing: 1.6px; text-transform: uppercase;
}}
QLabel[role="subtitle"] {{ font-size: {SIZE_SUBTITLE}pt; color: {p.text_dim}; }}
QLabel[role="body"]     {{ font-size: {SIZE_BODY}pt; color: {p.text}; }}
QLabel[role="muted"]    {{ font-size: {SIZE_SMALL}pt; color: {p.text_dim}; }}
QLabel[role="caption"]  {{ font-size: {SIZE_CAPTION}pt; color: {p.text_faint}; }}
QLabel[role="mono"]     {{ font-family: {FONT_MONO}; font-size: {SIZE_SMALL}pt; color: {p.text_dim}; }}
QLabel[role="metric"]   {{ font-family: {FONT_MONO}; font-size: {SIZE_DISPLAY}pt; font-weight: 400; color: {p.text}; }}
QLabel[role="danger"]   {{ color: {p.red_text}; }}

/* ---------------------------------------------------------------- rail */
#Rail {{ background: {p.rail}; border-right: 1px solid {p.line}; }}
#RailBrand {{ font-family: {FONT_DISPLAY}; font-size: {SIZE_TITLE}pt; font-weight: 700; color: {p.text}; }}
#RailTag {{ font-family: {FONT_MONO}; font-size: {SIZE_MICRO}pt; color: {p.text_faint}; }}
#RailFoot {{ font-family: {FONT_MONO}; font-size: {SIZE_MICRO}pt; color: {p.text_faint}; }}
#RailFootLabel {{ font-size: {SIZE_MICRO}pt; font-weight: 700; color: {p.text_faint}; letter-spacing: 1.4px; }}

QPushButton[nav="true"] {{
    background: transparent;
    border: none;
    border-left: 2px solid transparent;
    border-radius: 0px;
    padding: 9px 12px 9px 14px;
    text-align: left;
    color: {p.text_dim};
    font-size: {SIZE_BODY}pt;
    font-weight: 500;
}}
QPushButton[nav="true"]:hover {{ background: {p.surface}; color: {p.text}; }}
QPushButton[nav="true"]:focus {{ border: none; border-left: 2px solid transparent; }}
QPushButton[nav="true"][current="true"] {{
    background: {p.surface_alt};
    border-left: 2px solid {p.accent};
    color: {p.text};
    font-weight: 600;
}}

/* --------------------------------------------------------------- cards */
#Card {{
    background: {p.surface};
    border: 1px solid {p.line};
    border-radius: {RADIUS_LG}px;
}}
#CardQuiet {{
    background: {p.surface_alt};
    border: 1px solid {p.line};
    border-radius: {RADIUS_MD}px;
}}
#Slate {{
    background: {p.surface};
    border: 1px solid {p.line_strong};
    border-top: none;
    border-bottom-left-radius: {RADIUS_LG}px;
    border-bottom-right-radius: {RADIUS_LG}px;
}}
#Dropzone {{
    background: {p.surface};
    border: 1px dashed {p.line_strong};
    border-radius: {RADIUS_LG}px;
}}
#Dropzone[hot="true"] {{ border: 1px solid {p.accent}; background: {p.surface_alt}; }}
#Divider {{ background: {p.line}; border: none; }}

/* ------------------------------------------------------------- buttons */
QPushButton {{
    background: {p.surface_alt};
    color: {p.text};
    border: 1px solid {p.line_strong};
    border-radius: {RADIUS_SM}px;
    padding: 7px 14px;
    font-size: {SIZE_BODY}pt;
    font-weight: 500;
}}
QPushButton:hover {{ background: {p.surface_hi}; border-color: {p.text_faint}; }}
QPushButton:pressed {{ background: {p.line}; }}
QPushButton:disabled {{ color: {p.text_faint}; border-color: {p.line}; background: {p.surface}; }}
QPushButton:focus {{ border: 1px solid {p.text_dim}; }}

QPushButton[variant="primary"] {{
    background: {p.accent};
    color: {p.on_accent};
    border: 1px solid {p.accent};
    font-weight: 600;
    padding: 9px 20px;
}}
QPushButton[variant="primary"]:hover {{ background: {p.accent_hover}; border-color: {p.accent_hover}; }}
QPushButton[variant="primary"]:pressed {{ background: {p.accent_press}; }}
QPushButton[variant="primary"]:focus {{ border: 1px solid {p.text_faint}; }}
QPushButton[variant="primary"]:disabled {{
    background: {p.surface_alt}; color: {p.text_faint}; border-color: {p.line};
}}
QPushButton[variant="ghost"] {{
    background: transparent; border: 1px solid transparent; color: {p.text_dim};
}}
QPushButton[variant="ghost"]:hover {{ background: {p.surface_alt}; color: {p.text}; border-color: {p.line}; }}
QPushButton[variant="danger"] {{
    background: transparent; color: {p.red_text}; border: 1px solid {p.red};
}}
QPushButton[variant="danger"]:hover {{ background: {p.red_soft}; }}
QPushButton[variant="link"] {{
    background: transparent; border: none; color: {p.text};
    padding: 2px 4px; text-align: left; font-weight: 600;
    text-decoration: underline;
}}
QPushButton[variant="link"]:hover {{ color: {p.text_dim}; }}
QPushButton[segment="true"] {{
    background: transparent; color: {p.text_dim}; border: 1px solid {p.line_strong};
}}
QPushButton[segment="true"][on="true"] {{
    background: {p.accent}; color: {p.on_accent}; border-color: {p.accent}; font-weight: 600;
}}

/* -------------------------------------------------------------- inputs */
QLineEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background: {field_bg};
    border: 1px solid {p.line_strong};
    border-radius: {RADIUS_SM}px;
    padding: 7px 10px;
    selection-background-color: {p.accent};
    selection-color: {p.on_accent};
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {p.text_faint}; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {p.accent};
}}
QLineEdit:disabled {{ color: {p.text_faint}; }}
QLineEdit[role="search"] {{ padding-left: 32px; border-radius: {RADIUS_SM}px; }}
QPlainTextEdit[role="code"] {{
    font-family: {FONT_MONO}; font-size: {SIZE_SMALL}pt;
    background: {p.canvas if mode == 'dark' else p.surface_alt}; color: {p.text_dim};
}}
QLineEdit[role="template"] {{ font-family: {FONT_MONO}; font-size: {SIZE_SMALL}pt; }}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    width: 0px; border: none;
}}

QComboBox {{
    background: {p.surface_alt};
    border: 1px solid {p.line_strong};
    border-radius: {RADIUS_SM}px;
    padding: 7px 10px;
    min-width: 120px;
}}
QComboBox:hover {{ background: {p.surface_hi}; border-color: {p.text_faint}; }}
QComboBox:focus {{ border-color: {p.accent}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {p.surface_hi};
    border: 1px solid {p.line_strong};
    border-radius: {RADIUS_SM}px;
    padding: 4px;
    selection-background-color: {p.accent};
    selection-color: {p.on_accent};
    outline: none;
}}

QCheckBox {{ spacing: 9px; color: {p.text}; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {p.line_strong};
    border-radius: 3px;
    background: {field_bg};
}}
QCheckBox::indicator:hover {{ border-color: {p.text_dim}; }}
QCheckBox::indicator:checked {{ background: {p.accent}; border-color: {p.accent}; {check_rule} }}
QCheckBox::indicator:indeterminate {{ background: {p.surface_hi}; border-color: {p.accent}; {dash_rule} }}

/* -------------------------------------------------------------- tables */
QTableView, QListView {{
    background: {p.surface};
    alternate-background-color: {p.surface};
    border: 1px solid {p.line};
    border-radius: {RADIUS_LG}px;
    gridline-color: transparent;
    outline: none;
    selection-background-color: {p.selection};
    selection-color: {p.text};
}}
QTableView::item {{ border: none; padding: 0px; }}
QTableView::item:hover {{ background: {p.surface_alt}; }}
QTableView::item:selected {{ background: {p.selection}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: {p.surface};
    color: {p.text_faint};
    border: none;
    border-bottom: 1px solid {p.line};
    padding: 10px 12px;
    font-size: {SIZE_MICRO}pt;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
}}
QHeaderView::section:hover {{ color: {p.text_dim}; }}

/* ---------------------------------------------------------- scrollbars */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{
    background: {p.line_strong}; border-radius: 3px; min-height: 34px;
}}
QScrollBar::handle:vertical:hover {{ background: {p.text_faint}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px 4px; }}
QScrollBar::handle:horizontal {{
    background: {p.line_strong}; border-radius: 3px; min-width: 34px;
}}
QScrollBar::handle:horizontal:hover {{ background: {p.text_faint}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0px; height: 0px; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollArea {{ border: none; background: transparent; }}

/* ------------------------------------------------------------ progress */
QProgressBar {{
    background: {p.surface_hi};
    border: none;
    border-radius: 2px;
    height: 4px;
    max-height: 4px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background: {p.accent}; border-radius: 2px; }}

/* --------------------------------------------------------------- menus */
QMenu {{
    background: {p.surface_hi};
    border: 1px solid {p.line_strong};
    border-radius: {RADIUS_MD}px;
    padding: 5px;
}}
QMenu::item {{ padding: 7px 26px 7px 12px; border-radius: {RADIUS_SM}px; }}
QMenu::item:selected {{ background: {p.accent}; color: {p.on_accent}; }}
QMenu::separator {{ height: 1px; background: {p.line}; margin: 5px 8px; }}

/* ------------------------------------------------------------- dialogs */
QMessageBox {{ background: {p.surface}; }}
QMessageBox QLabel {{ color: {p.text}; }}
QListWidget {{
    background: {p.surface};
    border: 1px solid {p.line};
    border-radius: {RADIUS_MD}px;
    outline: none;
    padding: 4px;
}}
QListWidget::item {{ padding: 9px 11px; border-radius: {RADIUS_SM}px; color: {p.text}; }}
QListWidget::item:hover {{ background: {p.surface_alt}; }}
QListWidget::item:selected {{ background: {p.surface_hi}; color: {p.text}; border-left: 2px solid {p.accent}; }}

QGroupBox {{
    border: 1px solid {p.line};
    border-radius: {RADIUS_MD}px;
    margin-top: {s['lg']}px;
    padding: {s['lg']}px {s['md']}px {s['md']}px {s['md']}px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {p.text_faint};
    font-size: {SIZE_MICRO}pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.4px;
}}
QSplitter::handle {{ background: {p.line}; }}
"""


# --------------------------------------------------------------- active theme

_active_mode: Mode = "dark"


def apply_theme(app, mode: Mode) -> None:
    """Set the palette everything else reads from, and restyle the app."""
    global _active_mode
    _active_mode = mode
    check_url, dash_url = _checkbox_images(mode)
    app.setStyleSheet(stylesheet(mode, check_url, dash_url))
    _repolish(app)


def _repolish(app) -> None:
    from PySide6.QtWidgets import QWidget

    for widget in app.allWidgets():
        if isinstance(widget, QWidget):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()


def active() -> Palette:
    return PALETTES[_active_mode]


def active_mode() -> Mode:
    return _active_mode
