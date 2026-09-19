"""Shared page scaffolding: a column with a comfortable measure that still fills the window."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from endslate.ui.theme import CONTENT_MAX, SPACE


class Page(QWidget):
    def __init__(self, window, scroll: bool = True, parent=None):
        super().__init__(parent)
        self.window_ref = window

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        holder = QWidget()
        holder.setMaximumWidth(CONTENT_MAX)
        holder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred if scroll else QSizePolicy.Expanding)
        self.column = QVBoxLayout(holder)
        self.column.setContentsMargins(SPACE["2xl"], SPACE["xl"], SPACE["2xl"], SPACE["xl"])
        self.column.setSpacing(SPACE["xl"])

        centre = QWidget()
        centre_layout = QHBoxLayout(centre)
        centre_layout.setContentsMargins(0, 0, 0, 0)
        centre_layout.setSpacing(0)
        centre_layout.addStretch(1)
        centre_layout.addWidget(holder, 20)
        centre_layout.addStretch(1)

        if scroll:
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setFrameShape(QScrollArea.NoFrame)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            area.setWidget(centre)
            outer.addWidget(area)
        else:
            outer.addWidget(centre)

    def add(self, widget: QWidget, stretch: int = 0) -> QWidget:
        self.column.addWidget(widget, stretch)
        return widget

    def add_layout(self, layout) -> None:
        self.column.addLayout(layout)

    def add_stretch(self) -> None:
        self.column.addStretch(1)
