"""The Needs you resolver: pick the right film, or type it in yourself."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from endslate.models import Candidate, Item


class ResolveDialog(QDialog):
    def __init__(self, item: Item, matcher=None, parent=None):
        super().__init__(parent)
        self.item = item
        self.matcher = matcher
        self.result_meta: Optional[dict] = None
        self.apply_to_show = False

        self.setWindowTitle("Resolve")
        self.resize(760, 520)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{item.video.path.name}</b>"))
        layout.addWidget(QLabel(str(item.video.path.parent)))
        if item.note:
            layout.addWidget(QLabel(item.note))

        search_box = QGroupBox("Search TMDB")
        search_layout = QHBoxLayout(search_box)
        self.query = QLineEdit(item.show_hint if item.is_tv else item.parsed.title)
        self.query.returnPressed.connect(self.search)
        self.year = QSpinBox()
        self.year.setRange(0, 2100)
        self.year.setSpecialValueText("any year")
        self.year.setValue(item.parsed.year or 0)
        button = QPushButton("Search")
        button.clicked.connect(self.search)
        search_layout.addWidget(self.query, 3)
        search_layout.addWidget(self.year, 1)
        search_layout.addWidget(button)
        layout.addWidget(search_box)

        self.results = QListWidget()
        self.results.itemDoubleClicked.connect(lambda _: self.accept())
        layout.addWidget(self.results, 1)
        self._fill(item.candidates)

        manual = QGroupBox("Or set it by hand")
        manual_layout = QFormLayout(manual)
        self.manual_title = QLineEdit(item.parsed.title)
        self.manual_year = QSpinBox()
        self.manual_year.setRange(0, 2100)
        self.manual_year.setSpecialValueText("no year")
        self.manual_year.setValue(item.parsed.year or 0)
        manual_layout.addRow("Title", self.manual_title)
        manual_layout.addRow("Year", self.manual_year)
        layout.addWidget(manual)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Use this")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _fill(self, candidates: list[Candidate]) -> None:
        self.results.clear()
        for candidate in candidates:
            row = QListWidgetItem(f"{candidate.label}    ({candidate.score:.2f})\n{candidate.overview}")
            row.setData(Qt.UserRole, candidate)
            self.results.addItem(row)
        if candidates:
            self.results.setCurrentRow(0)

    def search(self) -> None:
        if self.matcher is None:
            QMessageBox.information(self, "No key", "Add a TMDB key in Settings to search.")
            return
        text = self.query.text().strip()
        if not text:
            return
        year = self.year.value() or None
        if self.item.is_tv:
            candidates = self.matcher.search_show(text, year)
        else:
            candidates = self.matcher.search_movie(text, year)
        for candidate in candidates:
            candidate.score = self.matcher._score(text, year, candidate)
        candidates.sort(key=lambda c: c.score, reverse=True)
        self._fill(candidates)
        if not candidates:
            QMessageBox.information(self, "Nothing found", f"TMDB returned no results for {text!r}.")

    def accept(self) -> None:
        row = self.results.currentItem()
        if row is not None and self.results.hasFocus() or (row is not None and not self.manual_title.isModified()):
            candidate: Candidate = row.data(Qt.UserRole)
            self.result_meta = {
                "title": candidate.title,
                "year": candidate.year,
                "tmdb_id": candidate.tmdb_id,
            }
        else:
            title = self.manual_title.text().strip()
            if not title:
                QMessageBox.warning(self, "Needs a title", "Pick a result or type a title.")
                return
            self.result_meta = {
                "title": title,
                "year": self.manual_year.value() or None,
                "tmdb_id": None,
            }
        self.apply_to_show = self.item.is_tv
        super().accept()
