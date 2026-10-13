"""The pieces the pages are assembled from. Every one reads the active palette.

Each is moulded from the surface by endslate.ui.neu: cards and buttons raised,
wells and inputs pressed in, and anything selected stays pressed in until it is
not. Widgets that need more than a body (the switch, the dial, the toast) paint
themselves with the same functions.
"""
from __future__ import annotations

import math
from typing import Callable, Optional

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from endslate.ui import icons, neu, theme
from endslate.ui.theme import RADIUS_BASE, RADIUS_CARD, RADIUS_INNER, SPACE, tone_colours


def label(text: str, role: str = "body", parent: Optional[QWidget] = None, wrap: Optional[bool] = None) -> QLabel:
    out = QLabel(text.upper() if role == "section" else text, parent)
    out.setProperty("role", role)
    theme.apply_role_font(out, role)
    out.setWordWrap(wrap if wrap is not None else role in ("subtitle", "muted", "body", "caption"))
    if out.wordWrap():
        out.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
    return out


def elide(widget: QLabel, text: str, mode=Qt.ElideMiddle) -> None:
    """Keep a long path on one line, trimmed to whatever width it has."""
    widget.setProperty("fullText", text)
    metrics = widget.fontMetrics()
    width = max(80, widget.width() - 4)
    widget.setText(metrics.elidedText(text, mode, width))
    widget.setToolTip(text)


def icon_label(name: str, size: int = 18, tone: str = "text_dim") -> QLabel:
    out = QLabel()
    out.setPixmap(icons.pixmap(name, getattr(theme.active(), tone), size))
    out.setFixedSize(size, size)
    return out


# ----------------------------------------------------------------- buttons


def mould_button(widget: QPushButton, variant: str = "default") -> QPushButton:
    """Give a push button its body for its variant."""
    widget.setProperty("variant", variant)
    widget.setCursor(Qt.PointingHandCursor)
    widget.setMinimumHeight(40)
    if variant == "link":
        return widget
    if variant == "primary":
        neu.style(widget, "raised", radius=RADIUS_BASE, depth="sm", interactive=True, fill="accent",
                  focus_ring=True, keyboard_ring=True)
    elif variant == "ghost":
        neu.style(widget, "raised", radius=RADIUS_INNER, depth="xs", interactive=True, hover_flat=True,
                  focus_ring=True, keyboard_ring=True)
    else:
        neu.style(widget, "raised", radius=RADIUS_BASE, depth="sm", interactive=True,
                  focus_ring=True, keyboard_ring=True)
    return widget


def button(text: str, variant: str = "default", icon_name: str = "", on_click=None) -> QPushButton:
    out = QPushButton(text)
    mould_button(out, variant)
    if icon_name:
        out.setProperty("iconName", icon_name)
        tint_button(out)
        out.setIconSize(QSize(17, 17))
    if on_click is not None:
        out.clicked.connect(on_click)
    return out


def tint_button(widget: QPushButton) -> None:
    """Colour a button's icon for its variant. Rerun on every theme change."""
    name = widget.property("iconName")
    if not name:
        return
    palette = theme.active()
    variant = widget.property("variant")
    if variant == "primary":
        colour = palette.on_accent if widget.isEnabled() else palette.text_faint
    elif variant == "danger":
        colour = palette.red_text
    elif widget.property("current") == "true" or (widget.isCheckable() and widget.isChecked()):
        colour = palette.accent
    else:
        colour = palette.text_dim
    widget.setIcon(icons.icon(name, colour, 17))


# ------------------------------------------------------------------ cards


class ClickableCard(QFrame):
    """A card that behaves like a button.

    Qt will not grow a QPushButton to fit a layout placed inside it, so a card
    built on one collides with its own text wherever the system font is larger
    than the one it was designed against. A frame sizes to its content.
    """

    clicked = Signal()

    def __init__(self, parent=None, radius: float = 22, depth: str = "md"):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setFocusPolicy(Qt.TabFocus)
        self._checked = False
        self._hover = False
        neu.style(self, "raised", radius=radius, depth=depth, interactive=True,
                  focus_ring=True, keyboard_ring=True)

    def isChecked(self) -> bool:  # noqa: N802
        return self._checked

    def setChecked(self, value: bool) -> None:  # noqa: N802
        self._checked = bool(value)
        neu.update_state(self)
        self.restyle()

    def restyle(self) -> None:  # overridden
        pass

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self.clicked.emit()
            return
        super().keyPressEvent(event)

    def enterEvent(self, event):  # noqa: N802
        self._hover = True
        self.restyle()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._hover = False
        self.restyle()
        super().leaveEvent(event)


class ElidedLabel(QLabel):
    """A label that trims itself instead of forcing the window wider.

    A long path in a non-wrapping label sets a minimum width, and a minimum width
    inside a page column pushes the whole layout past the window edge.
    """

    def __init__(self, text: str = "", role: str = "caption", mode=Qt.ElideMiddle, parent=None):
        super().__init__(parent)
        self.setProperty("role", role)
        theme.apply_role_font(self, role)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._mode = mode
        self._full = ""
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802
        self._full = text or ""
        self._apply()

    def fullText(self) -> str:  # noqa: N802
        return self._full

    def _apply(self) -> None:
        metrics = self.fontMetrics()
        width = max(60, self.width() - 2)
        super().setText(metrics.elidedText(self._full, self._mode, width))
        self.setToolTip(self._full)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._apply()


class Card(QFrame):
    """A panel raised from the surface. `quiet` presses it in instead."""

    def __init__(self, quiet: bool = False, padding: int = SPACE["xl"], parent=None):
        super().__init__(parent)
        self.setObjectName("CardQuiet" if quiet else "Card")
        if quiet:
            neu.style(self, "inset", radius=22, depth="md")
        else:
            neu.style(self, "raised", radius=RADIUS_CARD, depth="lg")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(SPACE["md"])

    def add(self, widget: QWidget, stretch: int = 0) -> QWidget:
        self.body.addWidget(widget, stretch)
        return widget

    def add_layout(self, layout) -> None:
        self.body.addLayout(layout)


class IconWell(QWidget):
    """An icon drilled into the surface: a round inset well, the glyph inside."""

    MARGIN = 10

    def __init__(self, icon_name: str, size: int = 44, glyph: int = 20, tone: str = "text_dim",
                 raised: bool = False, parent=None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.glyph = glyph
        self.tone = tone
        self.raised = raised
        self.setFixedSize(size + 2 * self.MARGIN, size + 2 * self.MARGIN)
        self._size = size

    def set_icon(self, icon_name: str, tone: Optional[str] = None) -> None:
        self.icon_name = icon_name
        if tone:
            self.tone = tone
        self.update()

    def restyle(self) -> None:
        self.update()

    def paintEvent(self, event):  # noqa: N802
        palette = theme.active()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.MARGIN, self.MARGIN, self._size, self._size)
        radius = self._size / 2
        if self.raised:
            neu.paint_raised(painter, rect, radius, neu.RAISED["xs"])
        else:
            neu.paint_inset(painter, rect, radius, neu.INSET["deep"] if self._size >= 56 else neu.INSET["md"])
        colour = getattr(palette, self.tone, None) or tone_colours(palette, self.tone)[0]
        pixmap = icons.pixmap(self.icon_name, colour, self.glyph)
        painter.drawPixmap(
            QPointF(rect.center().x() - self.glyph / 2, rect.center().y() - self.glyph / 2), pixmap
        )
        painter.end()


class Orb(QWidget):
    """The mark: concentric rings, extruded, pressed, extruded, around a violet core.

    It drifts on a three second breath, the one ambient motion in the app.
    """

    def __init__(self, size: int = 46, float_motion: bool = True, parent=None):
        super().__init__(parent)
        self._size = size
        self._phase = 0.0
        self.setFixedSize(size + 28, size + 28)
        self._anim = None
        if float_motion:
            anim = QVariantAnimation(self)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setDuration(3000)
            anim.setLoopCount(-1)
            anim.setEasingCurve(QEasingCurve.Linear)
            anim.valueChanged.connect(self._tick)
            anim.start()
            self._anim = anim

    def _tick(self, value) -> None:
        self._phase = float(value)
        self.update()

    def restyle(self) -> None:
        self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        bob = math.sin(self._phase * math.tau) * 1.5
        outer = QRectF(14, 14 + bob, self._size, self._size)
        neu.paint_raised(painter, outer, self._size / 2, neu.RAISED["sm"])
        ring = outer.adjusted(7, 7, -7, -7)
        neu.paint_inset(painter, ring, ring.width() / 2, neu.INSET["sm"])
        core = ring.adjusted(7, 7, -7, -7)
        neu.paint_raised(painter, core, core.width() / 2, neu.RAISED["xs"], fill=neu.accent_fill(core))
        painter.end()


# Kept so the old import name keeps working.
Clapstick = Orb


class Divider(QFrame):
    """An etched groove: a line of shade with a line of light under it."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Divider")
        self.setFixedHeight(2)

    def paintEvent(self, event):  # noqa: N802
        palette = theme.active()
        painter = QPainter(self)
        width = self.width()
        dark, dark_alpha = neu._rgba(palette.shadow_dark)
        light, light_alpha = neu._rgba(palette.shadow_light)
        shade = QColor(dark)
        shade.setAlphaF(min(1.0, dark_alpha * 0.8))
        glow = QColor(light)
        glow.setAlphaF(min(1.0, light_alpha * 1.2))
        painter.fillRect(0, 0, width, 1, shade)
        painter.fillRect(0, 1, width, 1, glow)
        painter.end()


class Pill(QLabel):
    """A small status chip, pressed into the surface, its words in the tone."""

    def __init__(self, text: str, tone: str = "neutral", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        theme.apply_role_font(self, "caption")
        neu.style(self, "inset", radius=theme.RADIUS_PILL, depth="sm")
        self.set_tone(tone)

    def set_tone(self, tone: str) -> None:
        self.tone = tone
        _strong, _soft, text = tone_colours(theme.active(), tone)
        self.setStyleSheet(
            f"background: transparent; color: {text}; border: none;"
            " padding: 4px 12px; font-weight: 700;"
        )

    def restyle(self) -> None:
        self.set_tone(self.tone)


class StatTile(ClickableCard):
    """A filter that shows its own count. Clicking it presses it in."""

    def __init__(self, key: str, title: str, tone: str, parent=None):
        super().__init__(parent, radius=22, depth="md")
        self.key = key
        self.tone = tone

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["lg"], SPACE["md"] + 2, SPACE["lg"], SPACE["md"] + 2)
        layout.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(SPACE["sm"])
        self.value = QLabel("0")
        self.value.setProperty("role", "metric")
        top.addWidget(self.value)
        top.addStretch(1)
        self.dot = QLabel()
        self.dot.setFixedSize(10, 10)
        top.addWidget(self.dot, 0, Qt.AlignTop)
        layout.addLayout(top)

        self.caption = QLabel(title)
        self.caption.setWordWrap(False)
        self.caption.setMinimumWidth(0)
        self._caption_text = title
        layout.addWidget(self.caption)
        self.restyle()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        elide(self.caption, self._caption_text, Qt.ElideRight)

    def set_count(self, count: int) -> None:
        self.value.setText(f"{count:,}")

    def restyle(self) -> None:
        palette = theme.active()
        strong, _soft, text = tone_colours(palette, self.tone)
        selected = self.isChecked()
        self.setObjectName("StatTile")
        self.setStyleSheet("#StatTile { background: transparent; border: none; }")
        self.dot.setStyleSheet(f"background: {strong}; border-radius: 5px; border: none;")
        self.caption.setFont(theme.font("caption", weight=700))
        self.caption.setStyleSheet(
            f"color: {text if selected else palette.text_faint};"
            f" font-family: {theme.FONT_DISPLAY}; font-size: {theme.SIZE_CAPTION}pt;"
            " font-weight: 700; background: transparent; border: none;"
        )
        # The family has to be in the rule as well: the app-wide QWidget rule
        # names the UI face and would win over setFont.
        self.value.setFont(theme.display_font(theme.SIZE_TITLE, 800))
        self.value.setStyleSheet(
            f"color: {palette.text if selected else palette.text_dim};"
            f" font-family: {theme.FONT_DISPLAY}; font-size: {theme.SIZE_TITLE}pt; font-weight: 800;"
            " background: transparent; border: none;"
        )


class Switch(QAbstractButton):
    """A toggle: a pressed-in track, a raised knob that slides along it."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFixedSize(68, 44)
        self._pos = 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(neu.DURATION)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._slide)

    def _get_knob(self) -> float:
        return self._pos

    def _set_knob(self, value: float) -> None:
        self._pos = float(value)
        self.update()

    knob = Property(float, _get_knob, _set_knob)

    def _slide(self, on: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def setChecked(self, value: bool) -> None:  # noqa: N802
        super().setChecked(value)
        if self._anim.state() != QPropertyAnimation.Running:
            self._pos = 1.0 if value else 0.0
            self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(68, 44)

    def restyle(self) -> None:
        self.update()

    def paintEvent(self, event):  # noqa: N802
        palette = theme.active()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        track = QRectF(8, 9, 52, 26)
        neu.paint_inset(painter, track, 13, neu.INSET["sm"], strength=1.0 if self.isEnabled() else 0.5)
        if self._pos > 0.01:
            painter.save()
            painter.setOpacity(self._pos if self.isEnabled() else self._pos * 0.4)
            fill = track.adjusted(2, 2, -2, -2)
            painter.setPen(Qt.NoPen)
            painter.setBrush(neu.accent_fill(fill))
            painter.drawRoundedRect(fill, 11, 11)
            painter.restore()
        travel = track.width() - 26
        knob = QRectF(track.left() + 3 + travel * self._pos, track.top() + 3, 20, 20)
        neu.paint_raised(painter, knob, 10, neu.RAISED["xs"])
        if self.hasFocus():
            neu.paint_ring(painter, track, 13, palette.accent, offset=3)
        painter.end()


class ToggleRow(QWidget):
    """A switch with the sentence that explains what it does."""

    toggled = Signal(bool)

    def __init__(self, title: str, description: str, checked: bool = True, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, SPACE["xs"], 0, SPACE["xs"])
        layout.setSpacing(SPACE["md"])

        text = QVBoxLayout()
        text.setSpacing(2)
        self.title = label(title, "strong", wrap=False)
        self.description = label(description, "caption", wrap=False)
        self.description.setMinimumWidth(0)
        self._description_text = description
        text.addWidget(self.title)
        text.addWidget(self.description)
        layout.addLayout(text, 1)

        self.check = Switch()
        self.check.setChecked(checked)
        self.check.toggled.connect(self.toggled.emit)
        self.check.setAccessibleName(title)
        layout.addWidget(self.check, 0, Qt.AlignVCenter)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        elide(self.description, self._description_text, Qt.ElideRight)

    def mouseReleaseEvent(self, event):  # noqa: N802
        # The whole row is the target, not only the switch.
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.check.toggle()
        super().mouseReleaseEvent(event)

    def isChecked(self) -> bool:  # noqa: N802
        return self.check.isChecked()

    def setChecked(self, value: bool) -> None:  # noqa: N802
        self.check.setChecked(value)


class PresetCard(ClickableCard):
    """A naming preset, shown with the two filenames it actually produces."""

    def __init__(self, name: str, description: str, example: str, parent=None):
        super().__init__(parent, radius=24, depth="md")
        self.preset_name = name

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["xl"], SPACE["lg"], SPACE["xl"], SPACE["lg"])
        layout.setSpacing(SPACE["xs"])
        layout.setSizeConstraint(QLayout.SetMinimumSize)

        header = QHBoxLayout()
        header.setSpacing(SPACE["sm"])
        self.title = QLabel(name)
        self.title.setProperty("role", "heading")
        theme.apply_role_font(self.title, "heading")
        self.mark = QLabel()
        self.mark.setFixedSize(18, 18)
        header.addWidget(self.title)
        header.addStretch(1)
        header.addWidget(self.mark, 0, Qt.AlignTop)
        layout.addLayout(header)

        self.description = QLabel(description)
        self.description.setWordWrap(True)
        self.description.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        theme.apply_role_font(self.description, "caption")
        layout.addWidget(self.description, 1)
        layout.addSpacing(SPACE["xs"])

        self.examples = [QLabel(""), QLabel("")]
        self._example_lines = example.split("\n")
        for line in self.examples:
            line.setWordWrap(False)
            line.setMinimumWidth(0)
            theme.apply_role_font(line, "mono")
            layout.addWidget(line)
        self.example = self.examples[0]
        self.restyle()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        for index, line in enumerate(self.examples):
            text = self._example_lines[index] if index < len(self._example_lines) else ""
            elide(line, text, Qt.ElideMiddle)

    def set_example(self, text: str) -> None:
        self._example_lines = text.split("\n")
        self._elide()

    def restyle(self) -> None:
        palette = theme.active()
        selected = self.isChecked()
        self.setObjectName("PresetCard")
        self.setStyleSheet(
            "#PresetCard { background: transparent; border: none; }"
            " QLabel { background: transparent; border: none; }"
        )
        theme.apply_role_font(self.title, "heading")
        self.title.setStyleSheet(
            f"color: {palette.accent_text if selected else palette.text};"
            f" font-family: {theme.FONT_DISPLAY}; font-weight: 700;"
        )
        theme.apply_role_font(self.description, "caption")
        self.description.setStyleSheet(f"color: {palette.text_faint};")
        for line in self.examples:
            theme.apply_role_font(line, "mono")
            line.setStyleSheet(
                f"color: {palette.text_dim if selected else palette.text_faint}; font-family: {theme.FONT_MONO};"
            )
        self.mark.setPixmap(icons.pixmap("check", palette.accent, 18) if selected else QPixmap())


class SearchField(QLineEdit):
    """A search well, its magnifier drilled into the left end."""

    def __init__(self, placeholder: str = "Search", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setProperty("role", "search")
        self.setClearButtonEnabled(True)
        self.setMinimumWidth(260)
        self.setMinimumHeight(44)
        neu.style(self, "inset", radius=RADIUS_BASE, depth="md", focus_ring=True)
        self._glyph = QLabel(self)
        self._glyph.setFixedSize(16, 16)
        self.restyle()

    def restyle(self) -> None:
        self._glyph.setPixmap(icons.pixmap("search", theme.active().text_faint, 16))

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._glyph.move(16, (self.height() - 16) // 2)


def well(widget: QWidget, radius: float = RADIUS_BASE, depth: str = "md") -> QWidget:
    """Press an input into the surface, with a focus ring when it has the caret."""
    neu.style(widget, "inset", radius=radius, depth=depth, focus_ring=True)
    widget.setMinimumHeight(max(widget.minimumHeight(), 42))
    return widget


def raised_control(widget: QWidget, radius: float = RADIUS_BASE) -> QWidget:
    """A control you operate rather than type into, such as a dropdown."""
    neu.style(widget, "raised", radius=radius, depth="sm", interactive=True, focus_ring=True,
              keyboard_ring=True)
    widget.setCursor(Qt.PointingHandCursor)
    widget.setMinimumHeight(max(widget.minimumHeight(), 42))
    return widget


class Banner(QFrame):
    """A message pressed into the surface, with its tone in the icon and the words."""

    def __init__(self, tone: str = "amber", icon_name: str = "warning", text: str = "", parent=None):
        super().__init__(parent)
        self.tone = tone
        self.icon_name = icon_name
        self.setObjectName("Banner")
        neu.style(self, "inset", radius=20, depth="sm")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE["lg"], SPACE["md"], SPACE["lg"], SPACE["md"])
        layout.setSpacing(SPACE["md"])

        self.glyph = IconWell(icon_name, size=30, glyph=16, raised=True)
        layout.addWidget(self.glyph, 0, Qt.AlignVCenter)

        self.text = label(text, "muted")
        layout.addWidget(self.text, 1)

        self.action = QPushButton()
        mould_button(self.action, "default")
        self.action.setVisible(False)
        layout.addWidget(self.action, 0, Qt.AlignVCenter)
        self.restyle()

    def show_message(self, text: str, tone: Optional[str] = None, icon_name: Optional[str] = None) -> None:
        if tone:
            self.tone = tone
        if icon_name:
            self.icon_name = icon_name
        self.text.setText(text)
        self.restyle()
        self.setVisible(bool(text))

    def set_action(self, text: str, handler: Callable[[], None]) -> None:
        self.action.setText(text)
        try:
            self.action.clicked.disconnect()
        except RuntimeError:
            pass
        self.action.clicked.connect(handler)
        self.action.setVisible(True)

    def restyle(self) -> None:
        # Selected by name: a bare QFrame rule would also hit the QLabel inside,
        # since QLabel is a QFrame, and draw a second box around the text.
        _strong, _soft, text_colour = tone_colours(theme.active(), self.tone)
        self.setStyleSheet("#Banner { background: transparent; border: none; }")
        self.glyph.set_icon(self.icon_name, self.tone)
        self.text.setStyleSheet(
            f"color: {text_colour}; background: transparent; border: none; font-weight: 500;"
        )


class EmptyState(QWidget):
    """What a panel says when it has nothing in it. Never a blank rectangle."""

    def __init__(self, icon_name: str, title: str, body: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["xl"], SPACE["3xl"], SPACE["xl"], SPACE["3xl"])
        layout.setSpacing(SPACE["md"])
        layout.setAlignment(Qt.AlignCenter)

        self.glyph = IconWell(icon_name, size=76, glyph=30, tone="text_faint")
        layout.addWidget(self.glyph, 0, Qt.AlignHCenter)
        layout.addSpacing(SPACE["xs"])

        self.title = label(title, "heading")
        self.title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title)

        self.body = label(body, "muted")
        self.body.setAlignment(Qt.AlignCenter)
        self.body.setMinimumWidth(380)
        self.body.setMaximumWidth(470)
        layout.addWidget(self.body, 0, Qt.AlignHCenter)

        self.icon_name = icon_name
        self.restyle()

    def set_text(self, title: str, body: str, icon_name: Optional[str] = None) -> None:
        self.title.setText(title)
        self.body.setText(body)
        if icon_name:
            self.icon_name = icon_name
        self.restyle()

    def restyle(self) -> None:
        palette = theme.active()
        self.glyph.set_icon(self.icon_name)
        self.title.setStyleSheet(f"color: {palette.text};")
        self.body.setStyleSheet(f"color: {palette.text_dim};")


class PageHeader(QWidget):
    """Title, one line of orientation, and the actions for this page."""

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE["lg"])

        text = QVBoxLayout()
        text.setSpacing(4)
        self.title = label(title, "title")
        self.subtitle = label(subtitle, "muted")
        text.addWidget(self.title)
        text.addWidget(self.subtitle)
        layout.addLayout(text, 1)

        self.actions = QHBoxLayout()
        self.actions.setSpacing(SPACE["md"])
        layout.addLayout(self.actions)

    def set_subtitle(self, text: str) -> None:
        self.subtitle.setText(text)

    def add_action(self, widget: QWidget) -> QWidget:
        self.actions.addWidget(widget, 0, Qt.AlignVCenter)
        return widget


class Toast(QWidget):
    """A short confirmation that floats up and fades. Never blocks anything."""

    PAD = 20

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.tone = "green"
        self.icon_name = "check"
        layout = QHBoxLayout(self)
        layout.setContentsMargins(self.PAD + SPACE["lg"], self.PAD + SPACE["md"],
                                  self.PAD + SPACE["lg"], self.PAD + SPACE["md"])
        layout.setSpacing(SPACE["md"])
        self.glyph = QLabel()
        self.glyph.setFixedSize(18, 18)
        self.text = label("", "body", wrap=False)
        layout.addWidget(self.glyph)
        layout.addWidget(self.text)
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.effect.setOpacity(0.0)
        self.hide()
        self._fade = QPropertyAnimation(self.effect, b"opacity", self)

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        body = QRectF(self.rect()).adjusted(self.PAD, self.PAD, -self.PAD, -self.PAD)
        neu.paint_raised(painter, body, body.height() / 2, neu.RAISED["md"])
        strong, _soft, _text = tone_colours(theme.active(), self.tone)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(strong))
        painter.drawEllipse(QRectF(body.left() + 9, body.center().y() - 3, 6, 6))
        painter.end()

    def show_message(self, text: str, icon_name: str = "check", tone: str = "green", msec: int = 2600) -> None:
        from PySide6.QtCore import QTimer

        palette = theme.active()
        self.tone = tone
        strong, _soft, _text = tone_colours(palette, tone)
        self.glyph.setPixmap(icons.pixmap(icon_name, strong, 18))
        self.text.setStyleSheet(f"color: {palette.text}; background: transparent; border: none; font-weight: 600;")
        self.text.setText(text)
        self.adjustSize()
        self._place()
        self.show()
        self.raise_()
        self._animate(1.0, 200)
        QTimer.singleShot(msec, lambda: self._animate(0.0, 360, hide=True))

    def _animate(self, target: float, duration: int, hide: bool = False) -> None:
        self._fade.stop()
        self._fade.setDuration(duration)
        self._fade.setStartValue(self.effect.opacity())
        self._fade.setEndValue(target)
        if hide:
            self._fade.finished.connect(self._maybe_hide)
        self._fade.start()

    def _maybe_hide(self) -> None:
        if self.effect.opacity() <= 0.01:
            self.hide()
        try:
            self._fade.finished.disconnect(self._maybe_hide)
        except RuntimeError:
            pass

    def _place(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.move(
            (parent.width() - self.width()) // 2,
            parent.height() - self.height() - SPACE["lg"],
        )


def restyle_tree(widget: QWidget) -> None:
    """Ask every themed component in a tree to recolour itself."""
    for child in widget.findChildren(QPushButton):
        tint_button(child)
    for child in widget.findChildren(QWidget):
        restyle = getattr(child, "restyle", None)
        if callable(restyle):
            restyle()
        if neu.spec_of(child) is not None:
            neu.update_state(child)
    widget.update()
