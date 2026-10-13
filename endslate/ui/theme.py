"""The design system: colour, type, depth, and the stylesheet built from them.

Soft UI on cool clay. Every surface is moulded from one grey (#E0E5EC by day,
a cool graphite by night) and told apart from the background by light alone: a
highlight falling from the top left, a shade falling to the bottom right. An
element is either extruded from the surface or pressed into it, never flat and
never outlined. Depth carries meaning: a card is raised, an input is a well, a
button sinks when it is pressed, and whatever is selected stays pressed in.

Colour is rationed. Violet is the hand: the one primary action on a screen, the
focus ring, the switch that is on. Four status hues say what will happen to a
file and nothing else: teal will move, amber needs you, rose collides, blue goes
to quarantine.

The shadows are painted by endslate.ui.neu. This module holds the tokens it
reads, and the stylesheet, which only ever sets text, spacing and the
transparent body every moulded widget wears so the paint beneath shows through.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Mode = Literal["dark", "light"]

FONTS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"

# DM Sans for reading, Plus Jakarta Sans for headlines, both bundled (SIL OFL).
# The fallbacks are what Windows always has.
UI_FAMILIES = ["DM Sans 9pt", "DM Sans", "Segoe UI Variable Text", "Segoe UI", "Noto Sans"]
DISPLAY_FAMILIES = ["Plus Jakarta Sans", "Segoe UI Variable Display", "Segoe UI"]
MONO_FAMILIES = ["Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono", "monospace"]


def _css(families: list[str], generic: str) -> str:
    return ", ".join(f'"{f}"' for f in families) + f", {generic}"


FONT_UI = _css(UI_FAMILIES, "sans-serif")
FONT_DISPLAY = _css(DISPLAY_FAMILIES, "sans-serif")
FONT_MONO = _css(MONO_FAMILIES[:-1], "monospace")

# Type scale, in points.
SIZE_HERO = 30
SIZE_DISPLAY = 26
SIZE_TITLE = 21
SIZE_SUBTITLE = 14
SIZE_BODY = 12
SIZE_SMALL = 11
SIZE_CAPTION = 10
SIZE_MICRO = 9

# Spacing. Open and airy, because a shadow needs room to fall.
SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 18, "xl": 26, "2xl": 34, "3xl": 48}

# Soft, pillowed corners: containers, controls, the things inside them.
RADIUS_CARD = 28
RADIUS_BASE = 16
RADIUS_INNER = 12
RADIUS_PILL = 999
# The old names, kept for anything that still asks for them.
RADIUS_SM = RADIUS_INNER
RADIUS_MD = RADIUS_BASE
RADIUS_LG = RADIUS_CARD

STRIPE_HEIGHT = 8
RAIL_WIDTH = 236
CONTENT_MAX = 1320
TOUCH = 44  # the smallest target anything clickable gets


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
    placeholder: str
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
    shadow_light: str
    shadow_dark: str


# Cool clay, straight from the design system. Text is #3D4852 (7.5:1) and
# nothing a person has to read is lighter than #6B7280 (4.6:1).
LIGHT = Palette(
    canvas="#E0E5EC",
    rail="#E0E5EC",
    surface="#E0E5EC",
    surface_alt="#E5EAF1",
    surface_hi="#D6DDE7",
    line="#CDD5E0",
    line_strong="#B9C3D1",
    text="#3D4852",
    text_dim="#4E5966",
    text_faint="#6B7280",
    placeholder="#8A94A6",
    accent="#6C63FF",
    accent_hover="#8B84FF",
    accent_press="#5A51F2",
    accent_soft="#D6D8F6",
    accent_text="#5149E0",
    on_accent="#FFFFFF",
    green="#38B2AC",
    green_soft="#D2E5E7",
    green_text="#1D6B66",
    amber="#D69E2E",
    amber_soft="#E9E0CF",
    amber_text="#7A5000",
    red="#E05767",
    red_soft="#EAD6DC",
    red_text="#A3243A",
    blue="#3F83D6",
    blue_soft="#D2DDEC",
    blue_text="#1D5799",
    selection="#D6DDE7",
    shade="#A3B1C6",
    shadow_light="rgba(255,255,255,0.62)",
    shadow_dark="rgba(163,177,198,0.68)",
)

# The same clay after dark: a cool graphite, the highlight a breath of white
# and the shade near black, so the moulding still reads.
DARK = Palette(
    canvas="#262A31",
    rail="#262A31",
    surface="#262A31",
    surface_alt="#2B3038",
    surface_hi="#343A44",
    line="#363C46",
    line_strong="#454C58",
    text="#E6E9EF",
    text_dim="#C2C9D3",
    text_faint="#9CA5B3",
    placeholder="#7F8897",
    accent="#7C74FF",
    accent_hover="#9C96FF",
    accent_press="#6A61F5",
    accent_soft="#35355A",
    accent_text="#ADA8FF",
    on_accent="#FFFFFF",
    green="#4FD1C5",
    green_soft="#223839",
    green_text="#82E3DA",
    amber="#F0B95B",
    amber_soft="#3A3324",
    amber_text="#F6D08E",
    red="#FF7B88",
    red_soft="#3E2830",
    red_text="#FFA8B1",
    blue="#64A6F2",
    blue_soft="#24324A",
    blue_text="#9FC8F8",
    selection="#2F343D",
    shade="#0E1013",
    shadow_light="rgba(255,255,255,0.075)",
    shadow_dark="rgba(6,8,12,0.62)",
)

PALETTES: dict[str, Palette] = {"dark": DARK, "light": LIGHT}

# Bucket to colour family, used by marks, dots and the filter tiles.
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
    if tone == "accent":
        return palette.accent, palette.accent_soft, palette.accent_text
    return (
        getattr(palette, tone),
        getattr(palette, f"{tone}_soft"),
        getattr(palette, f"{tone}_text"),
    )


def detect_mode() -> Mode:
    """Follow Windows' app theme when we can read it, otherwise assume light."""
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
    return "light"


def resolve_mode(preference: str) -> Mode:
    if preference in ("dark", "light"):
        return preference  # type: ignore[return-value]
    return detect_mode()


# ------------------------------------------------------------------- type

_fonts_loaded = False


def load_fonts() -> list[str]:
    """Register the bundled faces with Qt. Safe to call more than once."""
    global _fonts_loaded
    if _fonts_loaded:
        return []
    from PySide6.QtGui import QFontDatabase

    families: list[str] = []
    if FONTS_DIR.is_dir():
        for path in sorted(FONTS_DIR.glob("*.ttf")):
            index = QFontDatabase.addApplicationFont(str(path))
            if index >= 0:
                families += QFontDatabase.applicationFontFamilies(index)
    _fonts_loaded = True
    return sorted(set(families))


# role: (points, weight, family, letter spacing %). Headlines are set tight in
# Plus Jakarta Sans, as the design system asks; counts use it too, heavy, so a
# number reads as the most important thing on its tile.
ROLE_FONT = {
    "hero": (SIZE_HERO, 800, "display", 97),
    "display": (SIZE_DISPLAY, 800, "display", 97),
    "title": (SIZE_TITLE, 800, "display", 97),
    "heading": (SIZE_SUBTITLE, 700, "display", 99),
    "section": (SIZE_MICRO, 700, "display", 116),
    "subtitle": (SIZE_SUBTITLE, 500, "ui", 100),
    "body": (SIZE_BODY, 400, "ui", 100),
    "strong": (SIZE_BODY, 700, "ui", 100),
    "muted": (SIZE_SMALL, 400, "ui", 100),
    "caption": (SIZE_CAPTION, 400, "ui", 100),
    "mono": (SIZE_SMALL, 400, "mono", 100),
    "metric": (SIZE_DISPLAY, 800, "display", 96),
    "danger": (SIZE_SMALL, 500, "ui", 100),
}


def font(role: str = "body", points: int | None = None, weight: int | None = None):
    """A QFont for a role, with the family fallbacks set properly."""
    from PySide6.QtGui import QFont

    size, role_weight, family, spacing = ROLE_FONT.get(role, ROLE_FONT["body"])
    out = QFont()
    if family == "mono":
        out.setFamilies(MONO_FAMILIES)
        out.setStyleHint(QFont.Monospace)
    elif family == "display":
        out.setFamilies(DISPLAY_FAMILIES)
    else:
        out.setFamilies(UI_FAMILIES)
    out.setPointSize(points or size)
    out.setWeight(QFont.Weight(weight or role_weight))
    if spacing != 100:
        out.setLetterSpacing(QFont.PercentageSpacing, spacing)
    if family == "display" and (points or size) <= SIZE_CAPTION:
        # Plus Jakarta's space closes up at caption sizes: "Needsyou".
        out.setWordSpacing(2.0)
    return out


def mono_font(points: int = SIZE_SMALL, weight: int = 400):
    """The monospaced face with real fallbacks, for paths painted by hand."""
    return font("mono", points, weight)


def display_font(points: int = SIZE_TITLE, weight: int = 800):
    return font("display", points, weight)


def apply_role_font(widget, role: str) -> None:
    """Set the font in code as well as QSS.

    Qt computes a widget's size hint before the stylesheet lands, so a label that
    only gets its size from QSS reserves the wrong height and collides with its
    neighbour. Setting the font here keeps every layout honest.
    """
    widget.setFont(font(role))


# ------------------------------------------------------------- stylesheet


def _images(mode: Mode) -> dict[str, str]:
    """QSS cannot draw a tick or a chevron, so write them out and point at them."""
    from endslate.config import app_dir
    from endslate.ui import icons

    palette = PALETTES[mode]
    folder = app_dir() / "style"
    folder.mkdir(parents=True, exist_ok=True)
    wanted = {
        "check": ("check", palette.on_accent, 12),
        "dash": ("arrow-right", palette.accent, 12),
        "chevron": ("chevron-down", palette.text_dim, 14),
        "chevron_off": ("chevron-down", palette.text_faint, 14),
    }
    out: dict[str, str] = {}
    for key, (name, colour, size) in wanted.items():
        path = folder / f"{key}-{mode}.png"
        try:
            icons.pixmap(name, colour, size).save(str(path))
            out[key] = path.as_posix()
        except Exception:
            out[key] = ""
    return out


def stylesheet(mode: Mode, images: dict[str, str] | None = None) -> str:
    p = PALETTES[mode]
    images = images or {}

    def url(key: str) -> str:
        return f"image: url({images[key]});" if images.get(key) else ""

    return f"""
/* ---------------------------------------------------------------- base */
QWidget {{
    background: transparent;
    color: {p.text};
    font-family: {FONT_UI};
    font-size: {SIZE_BODY}pt;
}}
QMainWindow, QDialog, #Window {{ background: {p.canvas}; }}
QStatusBar {{ background: {p.canvas}; color: {p.text_faint}; border: none; }}
QStatusBar QLabel {{ color: {p.text_faint}; font-size: {SIZE_CAPTION}pt; }}
QToolTip {{
    background: {p.canvas};
    color: {p.text};
    border: 1px solid {p.line_strong};
    border-radius: {RADIUS_INNER}px;
    padding: 7px 11px;
    font-size: {SIZE_SMALL}pt;
}}

/* --------------------------------------------------------- typography */
QLabel[role="hero"]    {{ font-family: {FONT_DISPLAY}; font-size: {SIZE_HERO}pt; font-weight: 800; color: {p.text}; }}
QLabel[role="display"] {{ font-family: {FONT_DISPLAY}; font-size: {SIZE_DISPLAY}pt; font-weight: 800; color: {p.text}; }}
QLabel[role="title"]   {{ font-family: {FONT_DISPLAY}; font-size: {SIZE_TITLE}pt; font-weight: 800; color: {p.text}; }}
QLabel[role="heading"] {{ font-family: {FONT_DISPLAY}; font-size: {SIZE_SUBTITLE}pt; font-weight: 700; color: {p.text}; }}
QLabel[role="section"] {{
    font-family: {FONT_DISPLAY}; font-size: {SIZE_MICRO}pt; font-weight: 700; color: {p.text_faint};
    letter-spacing: 1.6px;
}}
QLabel[role="subtitle"] {{ font-size: {SIZE_SUBTITLE}pt; font-weight: 500; color: {p.text_dim}; }}
QLabel[role="body"]     {{ font-size: {SIZE_BODY}pt; color: {p.text}; }}
QLabel[role="strong"]   {{ font-size: {SIZE_BODY}pt; font-weight: 700; color: {p.text}; }}
QLabel[role="muted"]    {{ font-size: {SIZE_SMALL}pt; color: {p.text_dim}; }}
QLabel[role="caption"]  {{ font-size: {SIZE_CAPTION}pt; color: {p.text_faint}; }}
QLabel[role="mono"]     {{ font-family: {FONT_MONO}; font-size: {SIZE_SMALL}pt; color: {p.text_dim}; }}
QLabel[role="metric"]   {{ font-family: {FONT_DISPLAY}; font-size: {SIZE_DISPLAY}pt; font-weight: 800; color: {p.text}; }}
QLabel[role="danger"]   {{ color: {p.red_text}; }}

/* ---------------------------------------------------------------- rail */
#RailBrand {{ font-family: {FONT_DISPLAY}; font-size: {SIZE_TITLE}pt; font-weight: 800; color: {p.text}; }}
#RailTag {{ font-family: {FONT_DISPLAY}; font-size: {SIZE_MICRO}pt; font-weight: 700; color: {p.text_faint}; letter-spacing: 1.4px; }}
#RailFoot {{ font-family: {FONT_MONO}; font-size: {SIZE_MICRO}pt; color: {p.text_faint}; }}
#RailFootLabel {{ font-family: {FONT_DISPLAY}; font-size: {SIZE_MICRO}pt; font-weight: 700; color: {p.text_faint}; letter-spacing: 1.4px; }}

/* ------------------------------------------------------------- buttons */
/* Anything Qt builds itself (message boxes, file dialogs) keeps a plain
   soft body. Endslate's own buttons are moulded and wear neu="true". */
QPushButton {{
    background: {p.surface_hi};
    color: {p.text};
    border: none;
    border-radius: {RADIUS_INNER}px;
    padding: 9px 18px;
    min-height: 20px;
    font-size: {SIZE_BODY}pt;
    font-weight: 600;
}}
QPushButton:hover {{ background: {p.line}; }}
QPushButton:disabled {{ color: {p.text_faint}; }}
QPushButton[neu="true"] {{ background: transparent; padding: 10px 20px; }}
QPushButton[neu="true"]:hover {{ background: transparent; }}
QPushButton:focus {{ outline: none; }}

QPushButton[variant="primary"] {{ color: {p.on_accent}; font-weight: 700; padding: 11px 24px; }}
QPushButton[variant="primary"]:disabled {{ color: {p.text_faint}; }}
QPushButton[variant="ghost"] {{ color: {p.text_dim}; padding: 9px 14px; }}
QPushButton[variant="ghost"]:hover {{ color: {p.text}; }}
QPushButton[variant="danger"] {{ color: {p.red_text}; }}
QPushButton[variant="link"] {{
    background: transparent; color: {p.accent_text};
    padding: 2px 4px; text-align: left; font-weight: 700;
    text-decoration: underline;
}}
QPushButton[nav="true"] {{
    text-align: left;
    padding: 12px 18px;
    color: {p.text_dim};
    font-size: {SIZE_BODY}pt;
    font-weight: 500;
}}
QPushButton[nav="true"]:hover {{ color: {p.text}; }}
QPushButton[nav="true"][current="true"] {{ color: {p.text}; font-weight: 700; }}

/* -------------------------------------------------------------- inputs */
QLineEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background: {p.surface_hi};
    border: none;
    border-radius: {RADIUS_INNER}px;
    padding: 9px 14px;
    selection-background-color: {p.accent};
    selection-color: {p.on_accent};
}}
QLineEdit[neu="true"], QSpinBox[neu="true"], QDoubleSpinBox[neu="true"],
QPlainTextEdit[neu="true"], QTextEdit[neu="true"] {{ background: transparent; padding: 10px 16px; }}
QLineEdit:disabled {{ color: {p.text_faint}; }}
QLineEdit[role="search"] {{ padding-left: 40px; }}
QPlainTextEdit[role="code"] {{
    font-family: {FONT_MONO}; font-size: {SIZE_SMALL}pt; color: {p.text_dim};
    padding: 14px 18px;
}}
QLineEdit[role="template"] {{ font-family: {FONT_MONO}; font-size: {SIZE_SMALL}pt; }}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    width: 0px; border: none;
}}

QComboBox {{
    background: {p.surface_hi};
    border: none;
    border-radius: {RADIUS_INNER}px;
    padding: 9px 14px;
    padding-right: 36px;
    min-width: 120px;
    font-weight: 600;
}}
QComboBox[neu="true"] {{ background: transparent; padding: 10px 18px; padding-right: 40px; }}
QComboBox::drop-down {{ border: none; width: 34px; subcontrol-position: center right; }}
QComboBox::down-arrow {{ {url("chevron")} width: 14px; height: 14px; }}
QComboBox::down-arrow:disabled {{ {url("chevron_off")} }}
QComboBox QAbstractItemView {{
    background: {p.canvas};
    border: 1px solid {p.line_strong};
    border-radius: {RADIUS_INNER}px;
    padding: 6px;
    selection-background-color: {p.accent};
    selection-color: {p.on_accent};
    outline: none;
}}

QCheckBox {{ spacing: 10px; color: {p.text}; }}
QCheckBox::indicator {{
    width: 18px; height: 18px;
    border: none;
    border-radius: 6px;
    background: {p.surface_hi};
}}
QCheckBox::indicator:checked {{ background: {p.accent}; {url("check")} }}
QCheckBox::indicator:indeterminate {{ background: {p.surface_hi}; {url("dash")} }}

/* -------------------------------------------------------------- tables */
QTableView, QListView, QListWidget {{
    background: transparent;
    alternate-background-color: transparent;
    border: none;
    gridline-color: transparent;
    outline: none;
    selection-background-color: transparent;
    selection-color: {p.text};
}}
QTableView::item, QListView::item, QListWidget::item {{ border: none; padding: 0px; background: transparent; }}
QTableView::item:selected, QListWidget::item:selected {{ background: transparent; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: transparent; color: {p.text_faint}; border: none;
    padding: 10px 12px; font-size: {SIZE_MICRO}pt; font-weight: 700;
}}

/* ---------------------------------------------------------- scrollbars */
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 8px 3px; }}
QScrollBar::handle:vertical {{ background: {p.shade}; border-radius: 3px; min-height: 40px; }}
QScrollBar::handle:vertical:hover {{ background: {p.text_faint}; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 3px 8px; }}
QScrollBar::handle:horizontal {{ background: {p.shade}; border-radius: 3px; min-width: 40px; }}
QScrollBar::handle:horizontal:hover {{ background: {p.text_faint}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0px; height: 0px; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollArea {{ border: none; background: transparent; }}

/* ------------------------------------------------------------ progress */
QProgressBar {{
    background: transparent;
    border: none;
    border-radius: 6px;
    min-height: 12px;
    max-height: 12px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {p.accent_hover}, stop:1 {p.accent});
    border-radius: 6px;
    margin: 2px;
}}

/* --------------------------------------------------------------- menus */
QMenu {{
    background: {p.canvas};
    border: 1px solid {p.line_strong};
    border-radius: {RADIUS_BASE}px;
    padding: 8px;
}}
QMenu::item {{ padding: 9px 30px 9px 14px; border-radius: {RADIUS_INNER - 2}px; }}
QMenu::item:selected {{ background: {p.accent}; color: {p.on_accent}; }}
QMenu::separator {{ height: 1px; background: {p.line}; margin: 6px 10px; }}

/* ------------------------------------------------------------- dialogs */
QMessageBox {{ background: {p.canvas}; }}
QMessageBox QLabel {{ color: {p.text}; }}
QGroupBox {{
    border: none;
    margin-top: {SPACE['lg']}px;
    padding: {SPACE['lg']}px {SPACE['md']}px {SPACE['md']}px {SPACE['md']}px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 12px; padding: 0 6px;
    color: {p.text_faint}; font-size: {SIZE_MICRO}pt; font-weight: 700;
}}
QSplitter::handle {{ background: {p.line}; }}
"""


# --------------------------------------------------------------- active theme

_active_mode: Mode = "light"


def apply_theme(app, mode: Mode) -> None:
    """Set the palette everything else reads from, and restyle the app."""
    global _active_mode
    _active_mode = mode
    load_fonts()
    from PySide6.QtGui import QColor, QPalette

    p = PALETTES[mode]
    qt = app.palette()
    for role, value in (
        (QPalette.Window, p.canvas), (QPalette.Base, p.canvas), (QPalette.AlternateBase, p.surface_alt),
        (QPalette.Button, p.canvas), (QPalette.Text, p.text), (QPalette.WindowText, p.text),
        (QPalette.ButtonText, p.text), (QPalette.Highlight, p.accent), (QPalette.HighlightedText, p.on_accent),
        (QPalette.ToolTipBase, p.canvas), (QPalette.ToolTipText, p.text), (QPalette.PlaceholderText, p.placeholder),
        (QPalette.Link, p.accent_text),
    ):
        qt.setColor(role, QColor(value))
    app.setPalette(qt)
    app.setStyleSheet(stylesheet(mode, _images(mode)))
    from endslate.ui import neu

    neu.restyle_all()
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
