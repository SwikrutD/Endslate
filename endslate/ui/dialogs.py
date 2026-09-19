"""The resolver: which film is this, really.

Two films called The Witch a year apart look identical in a list, so the poster
is shown next to each candidate. That one image settles most of these.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from endslate.models import Candidate, Item
from endslate.ui import icons, theme
from endslate.ui.theme import RADIUS_MD, RADIUS_SM, SPACE
from endslate.ui.widgets import Banner, Card, Divider, EmptyState, SearchField, button, label

POSTER_BASE = "https://image.tmdb.org/t/p/w154"
POSTER_SIZE = QSize(62, 93)


class PosterFetcher(QThread):
    """Poster images, fetched off the UI thread and cached for the session."""

    ready = Signal(int, bytes)

    _cache: dict[int, bytes] = {}

    def __init__(self, jobs: list[tuple[int, str]], parent=None):
        super().__init__(parent)
        self.jobs = jobs

    def run(self) -> None:
        try:
            import requests
        except ImportError:
            return
        for tmdb_id, path in self.jobs:
            if tmdb_id in PosterFetcher._cache:
                self.ready.emit(tmdb_id, PosterFetcher._cache[tmdb_id])
                continue
            try:
                response = requests.get(f"{POSTER_BASE}{path}", timeout=8)
                if response.status_code == 200:
                    PosterFetcher._cache[tmdb_id] = response.content
                    self.ready.emit(tmdb_id, response.content)
            except Exception:
                continue


class CandidateRow(QWidget):
    def __init__(self, candidate: Candidate, parent=None):
        super().__init__(parent)
        self.candidate = candidate
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE["sm"], SPACE["sm"], SPACE["sm"], SPACE["sm"])
        layout.setSpacing(SPACE["md"])

        self.poster = QLabel()
        self.poster.setFixedSize(POSTER_SIZE)
        self.poster.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.poster)

        text = QVBoxLayout()
        text.setSpacing(3)
        self.title = label(candidate.label, "subtitle")
        self.overview = label(candidate.overview or "No summary on TMDB.", "caption")
        self.overview.setWordWrap(True)
        self.overview.setMaximumHeight(52)
        text.addWidget(self.title)
        text.addWidget(self.overview)
        text.addStretch(1)
        layout.addLayout(text, 1)

        self.score = label(f"{candidate.score:.2f}", "caption")
        self.score.setAlignment(Qt.AlignTop | Qt.AlignRight)
        layout.addWidget(self.score)
        self.restyle()

    def set_poster(self, data: bytes) -> None:
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            self.poster.setPixmap(
                pixmap.scaled(POSTER_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

    def restyle(self) -> None:
        palette = theme.active()
        if self.poster.pixmap() is None or self.poster.pixmap().isNull():
            self.poster.setPixmap(icons.pixmap("film", palette.line_strong, 26))
        self.poster.setStyleSheet(
            f"background: {palette.surface_alt}; border: 1px solid {palette.line};"
            f"border-radius: {RADIUS_SM}px;"
        )


class ResolveDialog(QDialog):
    def __init__(self, item: Item, matcher=None, parent=None):
        super().__init__(parent)
        self.item = item
        self.matcher = matcher
        self.result_meta: Optional[dict] = None
        self.apply_to_show = False
        self.rows: dict[int, CandidateRow] = {}
        self.fetcher: Optional[PosterFetcher] = None

        self.setWindowTitle("Which one is this?")
        self.setMinimumSize(760, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["xl"], SPACE["xl"], SPACE["xl"], SPACE["xl"])
        layout.setSpacing(SPACE["lg"])

        subject = Card(quiet=True, padding=SPACE["md"])
        subject.add(label(item.video.path.name, "body"))
        path_label = label(str(item.video.path.parent), "mono")
        path_label.setWordWrap(True)
        subject.add(path_label)
        layout.addWidget(subject)

        if item.note:
            note = Banner("amber", "info", item.note)
            layout.addWidget(note)

        search_row = QHBoxLayout()
        search_row.setSpacing(SPACE["sm"])
        self.query = SearchField("Title to search for")
        self.query.setText(item.show_hint if item.is_tv else item.parsed.title)
        self.query.returnPressed.connect(self.search)
        search_row.addWidget(self.query, 1)
        self.year = QSpinBox()
        self.year.setRange(0, 2100)
        self.year.setSpecialValueText("any year")
        self.year.setValue(item.parsed.year or 0)
        self.year.setFixedWidth(120)
        search_row.addWidget(self.year)
        search_row.addWidget(button("Search TMDB", "default", "search", self.search))
        layout.addLayout(search_row)

        self.results = QListWidget()
        self.results.setSpacing(2)
        self.results.itemDoubleClicked.connect(lambda _: self.accept())
        self.results.setSelectionMode(QListWidget.SingleSelection)
        layout.addWidget(self.results, 1)

        self.empty = EmptyState(
            "search",
            "No candidates yet" if not item.candidates else "",
            "Search TMDB, or type the title and year in below.",
        )
        layout.addWidget(self.empty)
        self._fill(item.candidates)

        layout.addWidget(Divider())
        manual_row = QHBoxLayout()
        manual_row.setSpacing(SPACE["sm"])
        manual_row.addWidget(label("Or set it by hand", "muted"))
        self.manual_title = QLineEdit(item.parsed.title)
        self.manual_title.setPlaceholderText("Title")
        manual_row.addWidget(self.manual_title, 1)
        self.manual_year = QSpinBox()
        self.manual_year.setRange(0, 2100)
        self.manual_year.setSpecialValueText("no year")
        self.manual_year.setValue(item.parsed.year or 0)
        self.manual_year.setFixedWidth(120)
        manual_row.addWidget(self.manual_year)
        self.use_manual = button("Use this", "default", "check", self._accept_manual)
        manual_row.addWidget(self.use_manual)
        layout.addLayout(manual_row)

        footer = QHBoxLayout()
        footer.setSpacing(SPACE["sm"])
        self.hint = label(
            "This applies to the whole show." if item.is_tv else "This applies to this film.",
            "caption",
        )
        footer.addWidget(self.hint, 1)
        footer.addWidget(button("Cancel", "ghost", "", self.reject))
        self.confirm = button("Use the selected result", "primary", "check", self._accept_selected)
        footer.addWidget(self.confirm)
        layout.addLayout(footer)

    # ------------------------------------------------------------------ list

    def _fill(self, candidates: list[Candidate]) -> None:
        self.results.clear()
        self.rows = {}
        jobs: list[tuple[int, str]] = []
        for candidate in candidates:
            row = CandidateRow(candidate)
            entry = QListWidgetItem(self.results)
            entry.setSizeHint(QSize(0, 110))
            entry.setData(Qt.UserRole, candidate)
            self.results.addItem(entry)
            self.results.setItemWidget(entry, row)
            self.rows[candidate.tmdb_id] = row
            poster = getattr(candidate, "poster_path", "")
            if poster:
                jobs.append((candidate.tmdb_id, poster))
        self.results.setVisible(bool(candidates))
        self.empty.setVisible(not candidates)
        self.confirm.setEnabled(bool(candidates))
        if candidates:
            self.results.setCurrentRow(0)
        if jobs:
            self.fetcher = PosterFetcher(jobs, self)
            self.fetcher.ready.connect(self._poster_ready)
            self.fetcher.start()

    def _poster_ready(self, tmdb_id: int, data: bytes) -> None:
        row = self.rows.get(tmdb_id)
        if row is not None:
            row.set_poster(data)

    def search(self) -> None:
        if self.matcher is None:
            self.empty.set_text(
                "No TMDB key",
                "Add a key on the Settings screen to search. You can still set the title by hand below.",
                "key",
            )
            self.results.setVisible(False)
            self.empty.setVisible(True)
            return
        text = self.query.text().strip()
        if not text:
            return
        year = self.year.value() or None
        candidates = (
            self.matcher.search_show(text, year) if self.item.is_tv else self.matcher.search_movie(text, year)
        )
        for candidate in candidates:
            candidate.score = self.matcher._score(text, year, candidate)
        candidates.sort(key=lambda c: (bool(year and c.year == year), c.score), reverse=True)
        self._fill(candidates)
        if not candidates:
            self.empty.set_text("Nothing found", f"TMDB returned no results for {text!r}.", "search")

    # ---------------------------------------------------------------- accept

    def _accept_selected(self) -> None:
        row = self.results.currentItem()
        if row is None:
            return
        candidate: Candidate = row.data(Qt.UserRole)
        self.result_meta = {
            "title": candidate.title,
            "year": candidate.year,
            "tmdb_id": candidate.tmdb_id,
        }
        self.apply_to_show = self.item.is_tv
        self.accept()

    def _accept_manual(self) -> None:
        title = self.manual_title.text().strip()
        if not title:
            return
        self.result_meta = {
            "title": title,
            "year": self.manual_year.value() or None,
            "tmdb_id": None,
        }
        self.apply_to_show = self.item.is_tv
        self.accept()

    def accept(self) -> None:
        if self.result_meta is None:
            self._accept_selected()
            if self.result_meta is None:
                return
        super().accept()
