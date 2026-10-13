"""The resolver: which film is this, really.

Two films called The Witch a year apart look identical in a list, so the poster
is shown next to each candidate. That one image settles most of these. Anime is
searched on TheTVDB, which lists the romaji and the English name side by side.
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
from endslate.ui import icons, neu, theme
from endslate.ui.theme import SPACE
from endslate.ui.widgets import Banner, Card, Divider, EmptyState, SearchField, button, label, well

POSTER_BASE = "https://image.tmdb.org/t/p/w154"
POSTER_SIZE = QSize(62, 93)


def poster_url(path: str) -> str:
    """TMDB hands back a path, TheTVDB a whole address."""
    return path if path.startswith("http") else f"{POSTER_BASE}{path}"


class PosterFetcher(QThread):
    """Poster images, fetched off the UI thread and cached for the session."""

    ready = Signal(str, bytes)

    _cache: dict[str, bytes] = {}

    def __init__(self, jobs: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.jobs = jobs

    def run(self) -> None:
        try:
            import requests
        except ImportError:
            return
        for key, path in self.jobs:
            if key in PosterFetcher._cache:
                self.ready.emit(key, PosterFetcher._cache[key])
                continue
            try:
                response = requests.get(poster_url(path), timeout=8)
                if response.status_code == 200:
                    PosterFetcher._cache[key] = response.content
                    self.ready.emit(key, response.content)
            except Exception:
                continue


class CandidateRow(QWidget):
    """One answer, raised from the list. The one you have chosen is pressed in."""

    def __init__(self, candidate: Candidate, parent=None):
        super().__init__(parent)
        self.candidate = candidate
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        neu.style(self, "raised", radius=20, depth="sm")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE["md"], SPACE["md"], SPACE["lg"], SPACE["md"])
        layout.setSpacing(SPACE["lg"])

        self.poster = QLabel()
        self.poster.setFixedSize(POSTER_SIZE)
        self.poster.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.poster)

        text = QVBoxLayout()
        text.setSpacing(3)
        self.title = label(candidate.label, "heading")
        aka = [a for a in candidate.aliases if a != candidate.title][:3]
        self.aka = label("also " + " · ".join(aka) if aka else "", "caption")
        self.aka.setVisible(bool(aka))
        self.overview = label(candidate.overview or "No summary from the provider.", "caption")
        self.overview.setWordWrap(True)
        self.overview.setMaximumHeight(52)
        text.addWidget(self.title)
        text.addWidget(self.aka)
        text.addWidget(self.overview)
        text.addStretch(1)
        layout.addLayout(text, 1)

        self.score = label(f"{candidate.score:.2f}", "caption")
        self.score.setAlignment(Qt.AlignTop | Qt.AlignRight)
        layout.addWidget(self.score)
        self._has_poster = False
        self.restyle()

    def set_selected(self, selected: bool) -> None:
        self.setProperty("neuPressed", selected)

    def set_poster(self, data: bytes) -> None:
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            self._has_poster = True
            self.poster.setPixmap(
                pixmap.scaled(POSTER_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

    def restyle(self) -> None:
        palette = theme.active()
        if not self._has_poster:
            self.poster.setPixmap(icons.pixmap("film", palette.text_faint, 26))
        self.poster.setStyleSheet(f"background: {palette.surface_hi}; border: none; border-radius: 10px;")


class ResolveDialog(QDialog):
    def __init__(self, item: Item, matcher=None, parent=None):
        super().__init__(parent)
        self.item = item
        self.matcher = matcher
        self.result_meta: Optional[dict] = None
        self.apply_to_show = False
        self.rows: dict[str, CandidateRow] = {}
        self.fetcher: Optional[PosterFetcher] = None
        provider = getattr(matcher, "provider_name", "TheTVDB" if item.is_anime and item.is_tv else "TMDB")

        self.setWindowTitle("Which one is this?")
        self.setMinimumSize(800, 660)

        # The dialog paints its own background after anything beneath it, so
        # the moulded parts live one level down, on a transparent sheet.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        sheet = neu.surface(QWidget())
        outer.addWidget(sheet)
        layout = QVBoxLayout(sheet)
        layout.setContentsMargins(SPACE["2xl"], SPACE["2xl"], SPACE["2xl"], SPACE["xl"])
        layout.setSpacing(SPACE["lg"])

        subject = Card(quiet=True, padding=SPACE["lg"])
        subject.add(label(item.video.path.name, "strong"))
        path_label = label(str(item.video.path.parent), "mono")
        path_label.setWordWrap(True)
        subject.add(path_label)
        layout.addWidget(subject)

        if item.note:
            note = Banner("amber", "info", item.note)
            layout.addWidget(note)

        search_row = QHBoxLayout()
        search_row.setSpacing(SPACE["md"])
        self.query = SearchField("Title to search for")
        self.query.setText(item.parsed.title or item.show_hint)
        self.query.returnPressed.connect(self.search)
        search_row.addWidget(self.query, 1)
        self.year = QSpinBox()
        self.year.setRange(0, 2100)
        self.year.setSpecialValueText("any year")
        self.year.setValue(item.parsed.year or 0)
        self.year.setFixedWidth(130)
        well(self.year)
        search_row.addWidget(self.year)
        search_row.addWidget(button(f"Search {provider}", "default", "search", self.search))
        layout.addLayout(search_row)

        self.results = QListWidget()
        self.results.setSpacing(10)
        self.results.itemDoubleClicked.connect(lambda _: self.accept())
        self.results.setSelectionMode(QListWidget.SingleSelection)
        self.results.currentItemChanged.connect(self._current_changed)
        layout.addWidget(self.results, 1)

        self.empty = EmptyState(
            "search",
            "No candidates yet" if not item.candidates else "",
            f"Search {provider}, or type the title and year in below.",
        )
        layout.addWidget(self.empty)

        layout.addWidget(Divider())
        manual_row = QHBoxLayout()
        manual_row.setSpacing(SPACE["md"])
        manual_row.addWidget(label("Or set it by hand", "muted"))
        self.manual_title = QLineEdit(item.parsed.title)
        self.manual_title.setPlaceholderText("Title")
        well(self.manual_title)
        manual_row.addWidget(self.manual_title, 1)
        self.manual_year = QSpinBox()
        self.manual_year.setRange(0, 2100)
        self.manual_year.setSpecialValueText("no year")
        self.manual_year.setValue(item.parsed.year or 0)
        self.manual_year.setFixedWidth(130)
        well(self.manual_year)
        manual_row.addWidget(self.manual_year)
        self.use_manual = button("Use this", "default", "check", self._accept_manual)
        manual_row.addWidget(self.use_manual)
        layout.addLayout(manual_row)

        footer = QHBoxLayout()
        footer.setSpacing(SPACE["md"])
        self.hint = label(
            "This applies to the whole show." if item.is_tv else "This applies to this film.",
            "caption",
        )
        footer.addWidget(self.hint, 1)
        footer.addWidget(button("Cancel", "ghost", "", self.reject))
        self.confirm = button("Use the selected result", "primary", "check", self._accept_selected)
        footer.addWidget(self.confirm)
        layout.addLayout(footer)

        # Filling the list touches the footer buttons, so it happens last.
        self._fill(item.candidates)

    # ------------------------------------------------------------------ list

    def _fill(self, candidates: list[Candidate]) -> None:
        self.results.clear()
        self.rows = {}
        jobs: list[tuple[str, str]] = []
        for candidate in candidates:
            row = CandidateRow(candidate)
            entry = QListWidgetItem(self.results)
            entry.setSizeHint(QSize(0, 124))
            entry.setData(Qt.UserRole, candidate)
            self.results.addItem(entry)
            self.results.setItemWidget(entry, row)
            self.rows[candidate.key] = row
            poster = getattr(candidate, "poster_path", "")
            if poster:
                jobs.append((candidate.key, poster))
        self.results.setVisible(bool(candidates))
        self.empty.setVisible(not candidates)
        self.confirm.setEnabled(bool(candidates))
        if candidates:
            self.results.setCurrentRow(0)
        if jobs:
            self.fetcher = PosterFetcher(jobs, self)
            self.fetcher.ready.connect(self._poster_ready)
            self.fetcher.start()

    def _current_changed(self, current, _previous) -> None:
        for index in range(self.results.count()):
            entry = self.results.item(index)
            row = self.results.itemWidget(entry)
            if isinstance(row, CandidateRow):
                row.set_selected(entry is current)

    def _poster_ready(self, key: str, data: bytes) -> None:
        row = self.rows.get(key)
        if row is not None:
            row.set_poster(data)

    def search(self) -> None:
        if self.matcher is None:
            self.empty.set_text(
                "No key for this search",
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
            provider = getattr(self.matcher, "provider_name", "TMDB")
            self.empty.set_text("Nothing found", f"{provider} returned no results for {text!r}.", "search")

    # ---------------------------------------------------------------- accept

    def _accept_selected(self) -> None:
        row = self.results.currentItem()
        if row is None:
            return
        candidate: Candidate = row.data(Qt.UserRole)
        self.result_meta = {
            "title": candidate.title,
            "year": candidate.year,
            "tmdb_id": None if candidate.tvdb_id else candidate.tmdb_id,
        }
        if candidate.tvdb_id:
            self.result_meta["tvdb_id"] = candidate.tvdb_id
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
