"""The pieces the pages are assembled from. Every one reads the active palette."""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QEvent, QPropertyAnimation, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QLayout,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from endslate.ui import icons, theme
from endslate.ui.theme import RADIUS_LG, RADIUS_MD, RADIUS_SM, SPACE, tone_colours


def label(text: str, role: str = "body", parent: Optional[QWidget] = None, wrap: Optional[bool] = None) -> QLabel:
    out = QLabel(text.upper() if role == "section" else text, parent)
    out.setProperty("role", role)
    theme.apply_role_font(out, role)
    out.setWordWrap(wrap if wrap is not None else role in ("subtitle", "muted", "body"))
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


def button(text: str, variant: str = "default", icon_name: str = "", on_click=None) -> QPushButton:
    out = QPushButton(text)
    out.setProperty("variant", variant)
    out.setCursor(Qt.PointingHandCursor)
    if icon_name:
        palette = theme.active()
        colour = palette.on_accent if variant == "primary" else palette.text_dim
        out.setIcon(icons.icon(icon_name, colour, 17))
        out.setIconSize(QSize(17, 17))
    if on_click is not None:
        out.clicked.connect(on_click)
    return out


class ClickableCard(QFrame):
    """A card that behaves like a button.

    Qt will not grow a QPushButton to fit a layout placed inside it, so a card
    built on one collides with its own text wherever the system font is larger
    than the one it was designed against. A frame sizes to its content.
    """

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._checked = False
        self._hover = False

    def isChecked(self) -> bool:  # noqa: N802
        return self._checked

    def setChecked(self, value: bool) -> None:  # noqa: N802
        self._checked = bool(value)
        self.restyle()

    def restyle(self) -> None:  # overridden
        pass

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def enterEvent(self, event):  # noqa: N802
        self._hover = True
        self.restyle()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._hover = False
        self.restyle()
        super().leaveEvent(event)


class Card(QFrame):
    """A panel. `quiet` is the inset variant used for nested blocks."""

    def __init__(self, quiet: bool = False, padding: int = SPACE["xl"], parent=None):
        super().__init__(parent)
        self.setObjectName("CardQuiet" if quiet else "Card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(SPACE["md"])

    def add(self, widget: QWidget, stretch: int = 0) -> QWidget:
        self.body.addWidget(widget, stretch)
        return widget

    def add_layout(self, layout) -> None:
        self.body.addLayout(layout)


class Divider(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Divider")
        self.setFixedHeight(1)


class Pill(QLabel):
    """A small status chip. Tone is one of the palette families."""

    def __init__(self, text: str, tone: str = "neutral", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        theme.apply_role_font(self, "caption")
        self.set_tone(tone)

    def set_tone(self, tone: str) -> None:
        strong, soft, text = tone_colours(theme.active(), tone)
        self.setStyleSheet(
            f"background: {soft}; color: {text}; border: 1px solid {strong};"
            f"border-radius: 9px; padding: 2px 9px; font-weight: 600;"
        )


class StatTile(ClickableCard):
    """A filter that shows its own count. Clicking it narrows the table."""

    def __init__(self, key: str, title: str, tone: str, parent=None):
        super().__init__(parent)
        self.key = key
        self.tone = tone

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["md"], SPACE["md"], SPACE["md"], SPACE["md"])
        layout.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(SPACE["sm"])
        self.value = QLabel("0")
        theme.apply_role_font(self.value, "metric")
        top.addWidget(self.value)
        top.addStretch(1)
        self.dot = QLabel()
        self.dot.setFixedSize(9, 9)
        top.addWidget(self.dot, 0, Qt.AlignTop)
        layout.addLayout(top)

        self.caption = QLabel(title)
        self.caption.setWordWrap(False)
        self.caption.setMinimumWidth(0)
        theme.apply_role_font(self.caption, "caption")
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
        strong, _soft, _text = tone_colours(palette, self.tone)
        selected = self.isChecked()
        background = palette.surface_alt if (selected or self._hover) else palette.surface
        border = strong if selected else (palette.line_strong if self._hover else palette.line)
        self.setStyleSheet(
            f"QFrame {{ background: {background}; border: 1px solid {border};"
            f" border-radius: {RADIUS_MD}px; }}"
        )
        self.dot.setStyleSheet(f"background: {strong}; border-radius: 4px; border: none;")
        theme.apply_role_font(self.caption, "caption")
        self.caption.setStyleSheet(
            f"color: {palette.text if selected else palette.text_dim};"
            " font-weight: 600; background: transparent; border: none;"
        )
        theme.apply_role_font(self.value, "metric")
        self.value.setStyleSheet(
            f"color: {palette.text if selected else palette.text_dim};"
            " background: transparent; border: none;"
        )


class ToggleRow(QWidget):
    """A checkbox with the sentence that explains what it does."""

    toggled = Signal(bool)

    def __init__(self, title: str, description: str, checked: bool = True, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, SPACE["xs"], 0, SPACE["xs"])
        layout.setSpacing(SPACE["md"])

        self.check = QCheckBox()
        self.check.setChecked(checked)
        self.check.setCursor(Qt.PointingHandCursor)
        self.check.toggled.connect(self.toggled.emit)
        layout.addWidget(self.check, 0, Qt.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(2)
        self.title = label(title, "body", wrap=False)
        self.description = label(description, "caption", wrap=False)
        self.description.setMinimumWidth(0)
        self._description_text = description
        text.addWidget(self.title)
        text.addWidget(self.description)
        layout.addLayout(text, 1)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        elide(self.description, self._description_text, Qt.ElideRight)

    def isChecked(self) -> bool:  # noqa: N802
        return self.check.isChecked()

    def setChecked(self, value: bool) -> None:  # noqa: N802
        self.check.setChecked(value)


class PresetCard(ClickableCard):
    """A naming preset, shown with the two filenames it actually produces."""

    def __init__(self, name: str, description: str, example: str, parent=None):
        super().__init__(parent)
        self.preset_name = name

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["lg"], SPACE["md"], SPACE["lg"], SPACE["md"])
        layout.setSpacing(SPACE["xs"])
        layout.setSizeConstraint(QLayout.SetMinimumSize)

        header = QHBoxLayout()
        header.setSpacing(SPACE["sm"])
        self.title = QLabel(name)
        theme.apply_role_font(self.title, "subtitle")
        self.mark = QLabel()
        self.mark.setFixedSize(16, 16)
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
        border = palette.accent if (selected or self._hover) else palette.line
        self.setStyleSheet(
            f"QFrame {{ background: {palette.accent_soft if selected else palette.surface};"
            f" border: 1px solid {border}; border-radius: {RADIUS_MD}px; }}"
            " QLabel { background: transparent; border: none; }"
        )
        theme.apply_role_font(self.title, "subtitle")
        self.title.setStyleSheet(f"color: {palette.text}; font-weight: 600;")
        theme.apply_role_font(self.description, "caption")
        self.description.setStyleSheet(f"color: {palette.text_dim};")
        for line in self.examples:
            theme.apply_role_font(line, "mono")
            line.setStyleSheet(f"color: {palette.accent_text if selected else palette.text_faint};")
        self.mark.setPixmap(
            icons.pixmap("check", palette.accent, 16) if selected else icons.pixmap("dot", palette.line, 16)
        )


class SearchField(QLineEdit):
    def __init__(self, placeholder: str = "Search", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setProperty("role", "search")
        self.setClearButtonEnabled(True)
        self.setMinimumWidth(260)
        self._glyph = QLabel(self)
        self._glyph.setFixedSize(16, 16)
        self.restyle()

    def restyle(self) -> None:
        self._glyph.setPixmap(icons.pixmap("search", theme.active().text_faint, 16))

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._glyph.move(10, (self.height() - 16) // 2)


class Banner(QFrame):
    """A one-line alert with a tone, used for the Jellyfin warning and results."""

    def __init__(self, tone: str = "amber", icon_name: str = "warning", text: str = "", parent=None):
        super().__init__(parent)
        self.tone = tone
        self.icon_name = icon_name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE["md"], SPACE["md"], SPACE["md"], SPACE["md"])
        layout.setSpacing(SPACE["md"])

        self.glyph = QLabel()
        self.glyph.setFixedSize(18, 18)
        layout.addWidget(self.glyph, 0, Qt.AlignTop)

        self.text = label(text, "muted")
        layout.addWidget(self.text, 1)

        self.action = QPushButton()
        self.action.setVisible(False)
        self.action.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.action, 0, Qt.AlignTop)
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
        strong, soft, text_colour = tone_colours(theme.active(), self.tone)
        self.setStyleSheet(
            f"QFrame {{ background: {soft}; border: 1px solid {strong};"
            f"border-radius: {RADIUS_MD}px; }}"
        )
        self.glyph.setPixmap(icons.pixmap(self.icon_name, strong, 18))
        self.text.setStyleSheet(f"color: {text_colour};")


class EmptyState(QWidget):
    """What a panel says when it has nothing in it. Never a blank rectangle."""

    def __init__(self, icon_name: str, title: str, body: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["xl"], SPACE["3xl"], SPACE["xl"], SPACE["3xl"])
        layout.setSpacing(SPACE["sm"])
        layout.setAlignment(Qt.AlignCenter)

        self.glyph = QLabel()
        self.glyph.setAlignment(Qt.AlignCenter)
        self.glyph.setFixedHeight(40)
        layout.addWidget(self.glyph)

        self.title = label(title, "subtitle")
        self.title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title)

        self.body = label(body, "muted")
        self.body.setAlignment(Qt.AlignCenter)
        self.body.setMinimumWidth(380)
        self.body.setMaximumWidth(460)
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
        self.glyph.setPixmap(icons.pixmap(self.icon_name, palette.line_strong, 34))
        self.title.setStyleSheet(f"color: {palette.text}; font-weight: 600;")
        self.body.setStyleSheet(f"color: {palette.text_dim};")


class PageHeader(QWidget):
    """Title, one line of orientation, and the actions for this page."""

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE["lg"])

        text = QVBoxLayout()
        text.setSpacing(2)
        self.title = label(title, "title")
        self.subtitle = label(subtitle, "muted")
        text.addWidget(self.title)
        text.addWidget(self.subtitle)
        layout.addLayout(text, 1)

        self.actions = QHBoxLayout()
        self.actions.setSpacing(SPACE["sm"])
        layout.addLayout(self.actions)

    def set_subtitle(self, text: str) -> None:
        self.subtitle.setText(text)

    def add_action(self, widget: QWidget) -> QWidget:
        self.actions.addWidget(widget)
        return widget


class Toast(QFrame):
    """A short confirmation that fades itself out. Never blocks anything."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE["md"], SPACE["sm"], SPACE["md"], SPACE["sm"])
        layout.setSpacing(SPACE["sm"])
        self.glyph = QLabel()
        self.glyph.setFixedSize(16, 16)
        self.text = label("", "muted", wrap=False)
        layout.addWidget(self.glyph)
        layout.addWidget(self.text)
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.effect.setOpacity(0.0)
        self.hide()
        self._fade = QPropertyAnimation(self.effect, b"opacity", self)

    def show_message(self, text: str, icon_name: str = "check", tone: str = "green", msec: int = 2600) -> None:
        from PySide6.QtCore import QTimer

        palette = theme.active()
        strong, _soft, _text = tone_colours(palette, tone)
        self.setStyleSheet(
            f"QFrame {{ background: {palette.surface_hi}; border: 1px solid {palette.line_strong};"
            f"border-radius: {RADIUS_SM}px; }}"
        )
        self.glyph.setPixmap(icons.pixmap(icon_name, strong, 16))
        self.text.setStyleSheet(f"color: {palette.text};")
        self.text.setText(text)
        self.adjustSize()
        self._place()
        self.show()
        self.raise_()
        self._animate(1.0, 160)
        QTimer.singleShot(msec, lambda: self._animate(0.0, 320, hide=True))

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
            parent.height() - self.height() - SPACE["xl"],
        )


def restyle_tree(widget: QWidget) -> None:
    """Ask every themed component in a tree to recolour itself."""
    for child in widget.findChildren(QWidget):
        restyle = getattr(child, "restyle", None)
        if callable(restyle):
            restyle()
