"""The design system: colour, type, spacing, and the stylesheet built from them.

One accent, borrowed from the app's clapperboard mark, and a neutral ramp that
stays out of the way. Everything a widget needs comes from the tokens below, so
the two themes stay in step and nothing hard-codes a colour.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Mode = Literal["dark", "light"]

FONT_UI = '"Segoe UI Variable Text", "Segoe UI", Inter, "Noto Sans", sans-serif'
FONT_MONO = '"Cascadia Mono", Consolas, "JetBrains Mono", "DejaVu Sans Mono", monospace'

# Type scale, in points. Small steps, because this is a dense tool.
SIZE_DISPLAY = 25
SIZE_TITLE = 18
SIZE_SUBTITLE = 14
SIZE_BODY = 13
SIZE_SMALL = 12
SIZE_CAPTION = 11
SIZE_MICRO = 10

# Spacing scale. Every margin and gap in the app is one of these.
SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "2xl": 32, "3xl": 44}

RADIUS_SM = 6
RADIUS_MD = 9
RADIUS_LG = 14

RAIL_WIDTH = 226
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


DARK = Palette(
    canvas="#0D0F13",
    rail="#111419",
    surface="#171A21",
    surface_alt="#1D212A",
    surface_hi="#242A35",
    line="#252A34",
    line_strong="#343B48",
    text="#E9ECF1",
    text_dim="#A2ABB9",
    text_faint="#6C7683",
    accent="#E87A3A",
    accent_hover="#F28C4E",
    accent_press="#D06A2E",
    accent_soft="#2C1D13",
    accent_text="#F5A873",
    on_accent="#1A0E06",
    green="#4FA96B",
    green_soft="#15251B",
    green_text="#82D29B",
    amber="#D9A13C",
    amber_soft="#261F13",
    amber_text="#EBC271",
    red="#D9564F",
    red_soft="#2A1716",
    red_text="#F28C86",
    blue="#5B8DEF",
    blue_soft="#151B2A",
    blue_text="#96B6F7",
    selection="#243040",
    shade="#000000",
)

LIGHT = Palette(
    canvas="#F4F6F8",
    rail="#FFFFFF",
    surface="#FFFFFF",
    surface_alt="#F3F5F8",
    surface_hi="#E8ECF2",
    line="#E1E6EC",
    line_strong="#C9D1DB",
    text="#111620",
    text_dim="#4F5A69",
    text_faint="#7C8695",
    accent="#C65B1B",
    accent_hover="#D96A26",
    accent_press="#A94A12",
    accent_soft="#FCEFE4",
    accent_text="#9B4512",
    on_accent="#FFFFFF",
    green="#1E7A46",
    green_soft="#E8F5ED",
    green_text="#186139",
    amber="#9A6B10",
    amber_soft="#FBF1DC",
    amber_text="#7C560C",
    red="#C0342E",
    red_soft="#FCEBEA",
    red_text="#9B2723",
    blue="#2F63C7",
    blue_soft="#EAF0FC",
    blue_text="#27529F",
    selection="#E2EBF8",
    shade="#8A94A6",
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


ROLE_FONT = {
    "display": (SIZE_DISPLAY, 600, False),
    "title": (SIZE_TITLE, 600, False),
    "section": (SIZE_CAPTION, 700, False),
    "subtitle": (SIZE_SUBTITLE, 400, False),
    "body": (SIZE_BODY, 400, False),
    "muted": (SIZE_SMALL, 400, False),
    "caption": (SIZE_CAPTION, 400, False),
    "mono": (SIZE_SMALL, 400, True),
    "metric": (SIZE_DISPLAY, 600, False),
    "danger": (SIZE_SMALL, 400, False),
}


def apply_role_font(widget, role: str) -> None:
    """Set the font in code as well as QSS.

    Qt computes a widget's size hint before the stylesheet lands, so a label that
    only gets its size from QSS reserves the wrong height and collides with its
    neighbour. Setting the font here keeps every layout honest.
    """
    from PySide6.QtGui import QFont

    size, weight, mono = ROLE_FONT.get(role, ROLE_FONT["body"])
    font = QFont(widget.font())
    if mono:
        font.setFamilies(["Cascadia Mono", "Consolas", "DejaVu Sans Mono", "monospace"])
        font.setStyleHint(QFont.Monospace)
    font.setPointSize(size)
    font.setWeight(QFont.Weight(weight))
    if role == "section":
        font.setLetterSpacing(QFont.PercentageSpacing, 112)
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
    return f"""
/* ---------------------------------------------------------------- base */
QWidget {{
    background: transparent;
    color: {p.text};
    font-family: {FONT_UI};
    font-size: {SIZE_BODY}pt;
}}
QMainWindow, QDialog {{ background: {p.canvas}; }}
QToolTip {{
    background: {p.surface_hi};
    color: {p.text};
    border: 1px solid {p.line_strong};
    border-radius: {RADIUS_SM}px;
    padding: 6px 9px;
    font-size: {SIZE_SMALL}pt;
}}

/* --------------------------------------------------------- typography */
QLabel[role="display"] {{ font-size: {SIZE_DISPLAY}pt; font-weight: 600; color: {p.text}; }}
QLabel[role="title"]   {{ font-size: {SIZE_TITLE}pt; font-weight: 600; color: {p.text}; }}
QLabel[role="section"] {{
    font-size: {SIZE_CAPTION}pt; font-weight: 700; color: {p.text_faint};
    letter-spacing: 1.2px; text-transform: uppercase;
}}
QLabel[role="subtitle"] {{ font-size: {SIZE_SUBTITLE}pt; color: {p.text_dim}; }}
QLabel[role="body"]     {{ font-size: {SIZE_BODY}pt; color: {p.text}; }}
QLabel[role="muted"]    {{ font-size: {SIZE_SMALL}pt; color: {p.text_dim}; }}
QLabel[role="caption"]  {{ font-size: {SIZE_CAPTION}pt; color: {p.text_faint}; }}
QLabel[role="mono"]     {{ font-family: {FONT_MONO}; font-size: {SIZE_SMALL}pt; color: {p.text_dim}; }}
QLabel[role="metric"]   {{ font-size: {SIZE_DISPLAY}pt; font-weight: 600; color: {p.text}; }}
QLabel[role="danger"]   {{ color: {p.red_text}; }}

/* ---------------------------------------------------------------- rail */
#Rail {{ background: {p.rail}; border-right: 1px solid {p.line}; }}
#RailBrand {{ font-size: {SIZE_TITLE}pt; font-weight: 700; color: {p.text}; }}
#RailTag {{ font-size: {SIZE_CAPTION}pt; color: {p.text_faint}; }}
#RailFoot {{ font-size: {SIZE_CAPTION}pt; color: {p.text_faint}; }}

QPushButton[nav="true"] {{
    background: transparent;
    border: none;
    border-radius: {RADIUS_MD}px;
    padding: 9px 12px;
    text-align: left;
    color: {p.text_dim};
    font-size: {SIZE_BODY}pt;
    font-weight: 500;
}}
QPushButton[nav="true"]:hover {{ background: {p.surface_alt}; color: {p.text}; }}
QPushButton[nav="true"][current="true"] {{
    background: {p.surface_hi};
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
#Dropzone {{
    background: {p.surface};
    border: 2px dashed {p.line_strong};
    border-radius: {RADIUS_LG}px;
}}
#Dropzone[hot="true"] {{ border-color: {p.accent}; background: {p.accent_soft}; }}
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
QPushButton:hover {{ background: {p.surface_hi}; }}
QPushButton:pressed {{ background: {p.line}; }}
QPushButton:disabled {{ color: {p.text_faint}; border-color: {p.line}; background: {p.surface}; }}
QPushButton:focus {{ border: 1px solid {p.accent}; }}

QPushButton[variant="primary"] {{
    background: {p.accent};
    color: {p.on_accent};
    border: 1px solid {p.accent};
    font-weight: 600;
    padding: 9px 20px;
}}
QPushButton[variant="primary"]:hover {{ background: {p.accent_hover}; border-color: {p.accent_hover}; }}
QPushButton[variant="primary"]:pressed {{ background: {p.accent_press}; }}
QPushButton[variant="primary"]:disabled {{
    background: {p.surface_alt}; color: {p.text_faint}; border-color: {p.line};
}}
QPushButton[variant="ghost"] {{
    background: transparent; border: 1px solid transparent; color: {p.text_dim};
}}
QPushButton[variant="ghost"]:hover {{ background: {p.surface_alt}; color: {p.text}; }}
QPushButton[variant="danger"] {{
    background: {p.red_soft}; color: {p.red_text}; border: 1px solid {p.red};
}}
QPushButton[variant="danger"]:hover {{ background: {p.red}; color: #fff; }}
QPushButton[variant="link"] {{
    background: transparent; border: none; color: {p.accent_text};
    padding: 2px 4px; text-align: left; font-weight: 500;
}}
QPushButton[variant="link"]:hover {{ color: {p.accent}; }}

/* -------------------------------------------------------------- inputs */
QLineEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background: {p.canvas if mode == 'dark' else p.surface};
    border: 1px solid {p.line_strong};
    border-radius: {RADIUS_SM}px;
    padding: 7px 10px;
    selection-background-color: {p.accent};
    selection-color: {p.on_accent};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {p.accent};
}}
QLineEdit:disabled {{ color: {p.text_faint}; }}
QLineEdit[role="search"] {{ padding-left: 32px; border-radius: {RADIUS_SM}px; }}
QPlainTextEdit[role="code"] {{ font-family: {FONT_MONO}; font-size: {SIZE_SMALL}pt; }}
QLineEdit[role="template"] {{ font-family: {FONT_MONO}; font-size: {SIZE_SMALL}pt; }}

QComboBox {{
    background: {p.surface_alt};
    border: 1px solid {p.line_strong};
    border-radius: {RADIUS_SM}px;
    padding: 7px 10px;
    min-width: 120px;
}}
QComboBox:hover {{ background: {p.surface_hi}; }}
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
    width: 17px; height: 17px;
    border: 1px solid {p.line_strong};
    border-radius: 5px;
    background: {p.canvas if mode == 'dark' else p.surface};
}}
QCheckBox::indicator:hover {{ border-color: {p.accent}; }}
QCheckBox::indicator:checked {{ background: {p.accent}; border-color: {p.accent}; {check_rule} }}
QCheckBox::indicator:indeterminate {{ background: {p.accent_soft}; border-color: {p.accent}; {dash_rule} }}

/* -------------------------------------------------------------- tables */
QTableView {{
    background: {p.surface};
    alternate-background-color: {p.surface};
    border: 1px solid {p.line};
    border-radius: {RADIUS_MD}px;
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
    font-size: {SIZE_CAPTION}pt;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}}
QHeaderView::section:hover {{ color: {p.text_dim}; }}

/* ---------------------------------------------------------- scrollbars */
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{
    background: {p.line_strong}; border-radius: 5px; min-height: 34px;
}}
QScrollBar::handle:vertical:hover {{ background: {p.text_faint}; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 2px 4px; }}
QScrollBar::handle:horizontal {{
    background: {p.line_strong}; border-radius: 5px; min-width: 34px;
}}
QScrollBar::handle:horizontal:hover {{ background: {p.text_faint}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0px; height: 0px; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollArea {{ border: none; background: transparent; }}

/* ------------------------------------------------------------ progress */
QProgressBar {{
    background: {p.surface_alt};
    border: none;
    border-radius: 4px;
    height: 7px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background: {p.accent}; border-radius: 4px; }}

/* --------------------------------------------------------------- menus */
QMenu {{
    background: {p.surface_hi};
    border: 1px solid {p.line_strong};
    border-radius: {RADIUS_MD}px;
    padding: 6px;
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
QListWidget::item:selected {{ background: {p.accent_soft}; color: {p.text}; }}

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
    font-size: {SIZE_CAPTION}pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
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
