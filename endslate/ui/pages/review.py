"""The screen the work happens on: every proposed change, filterable and searchable."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QMenu,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from endslate.models import Bucket
from endslate.ui import theme
from endslate.ui.delegate import ROW_HEIGHT, PlanRowDelegate
from endslate.ui.pages.base import Page
from endslate.ui.tablemodel import ENTRY_ROLE, SORT_KEYS, PlanFilterProxy, PlanTableModel
from endslate.ui.theme import SPACE
from endslate.ui.widgets import (
    Banner,
    Card,
    EmptyState,
    PageHeader,
    SearchField,
    StatTile,
    button,
    label,
)

TILES = [
    ("planned", "Planned", "green"),
    ("needs_you", "Needs you", "amber"),
    ("duplicate", "Duplicates", "red"),
    ("junk", "Junk", "blue"),
    ("noop", "Correct", "neutral"),
    ("skipped", "Skipped", "neutral"),
]

EMPTY_COPY = {
    "planned": ("check", "Nothing to rename", "Every file already matches the preset. Change the preset or the options to see more."),
    "needs_you": ("sparkle", "Nothing needs you", "Every title matched a film or show confidently."),
    "duplicate": ("copy", "No duplicates", "No two files want the same name."),
    "junk": ("trash", "No junk found", "No resource forks, adverts or empty folders in this library."),
    "noop": ("check", "Nothing already correct", "No file is sitting at the name the preset would give it."),
    "skipped": ("info", "Nothing skipped", "Every file was readable and every subtitle found its video."),
}


class ReviewPage(Page):
    def __init__(self, window, parent=None):
        super().__init__(window, scroll=False, parent=parent)
        self.column.setSpacing(SPACE["lg"])

        self.header = PageHeader("Review", "Scan a library to see what would change.")
        self.apply_button = button("Apply", "primary", "play", window.go_to_apply)
        self.apply_button.setEnabled(False)
        self.header.add_action(button("Rescan", "default", "refresh", window.start_scan))
        self.header.add_action(self.apply_button)
        self.add(self.header)

        # ------------------------------------------------------------- tiles
        tiles_holder = QWidget()
        tiles = QHBoxLayout(tiles_holder)
        tiles.setContentsMargins(0, 0, 0, 0)
        tiles.setSpacing(SPACE["sm"])
        self.tiles: dict[str, StatTile] = {}
        for key, title, tone in TILES:
            tile = StatTile(key, title, tone)
            tile.clicked.connect(lambda _=False, k=key: self.set_filter(k))
            tiles.addWidget(tile)
            self.tiles[key] = tile
        self.add(tiles_holder)

        # ----------------------------------------------------------- toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(SPACE["sm"])
        self.search = SearchField("Search titles and paths")
        self.search.textChanged.connect(self._search_changed)
        toolbar.addWidget(self.search)

        self.sort = QComboBox()
        self.sort.addItems([f"Sort by {key.lower()}" for key in SORT_KEYS])
        self.sort.setFixedWidth(184)
        self.sort.currentIndexChanged.connect(self._sort_changed)
        self.sort.setToolTip("Change the order of the list")
        toolbar.addWidget(self.sort)

        toolbar.addStretch(1)
        self.count_label = label("", "caption")
        toolbar.addWidget(self.count_label)
        toolbar.addWidget(button("All", "ghost", "", lambda: self._set_all(True)))
        toolbar.addWidget(button("None", "ghost", "", lambda: self._set_all(False)))
        self.resolve_button = button("Resolve", "default", "sparkle", self.resolve_selected)
        self.resolve_button.setToolTip("Search TMDB for this title, or set it by hand  (Enter)")
        toolbar.addWidget(self.resolve_button)
        self.add_layout(toolbar)

        # ------------------------------------------------------------- table
        self.model = PlanTableModel()
        self.proxy = PlanFilterProxy()
        self.proxy.setSourceModel(self.model)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setItemDelegate(PlanRowDelegate(self.model, self.table))
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setShowGrid(False)
        self.table.setMouseTracking(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        self.table.horizontalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.doubleClicked.connect(lambda _: self.resolve_selected())
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        self.empty = EmptyState("film", "Nothing scanned yet", "Choose a folder on the Library screen and press Scan.")
        self.stack = QStackedWidget()
        self.stack.addWidget(self.table)
        self.stack.addWidget(self.empty)
        self.stack.setCurrentWidget(self.empty)
        self.add(self.stack, 1)

        self.notes = Banner("blue", "info", "")
        self.notes.setVisible(False)
        self.add(self.notes)

        self.filter_key = "planned"
        self.plan = None
        self._install_shortcuts()

    # ------------------------------------------------------------- shortcuts

    def _install_shortcuts(self) -> None:
        def on_table(sequence, handler):
            shortcut = QShortcut(QKeySequence(sequence), self.table, activated=handler)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            return shortcut

        find = QShortcut(QKeySequence("Ctrl+F"), self, activated=self.search.setFocus)
        find.setContext(Qt.WidgetWithChildrenShortcut)
        on_table(Qt.Key_Space, self._toggle_selection)
        on_table(Qt.Key_Return, self.resolve_selected)
        on_table("Ctrl+A", lambda: self._set_all(True))

    # ------------------------------------------------------------------ data

    def set_plan(self, plan) -> None:
        self.plan = plan
        self.model.root = plan.root
        counts = plan.counts()
        for key, tile in self.tiles.items():
            tile.set_count(counts.get(key, 0))
        planned = counts.get("planned", 0)
        total_ops = len(plan.selected_operations())
        self.header.set_subtitle(
            f"{planned:,} changes ready, {counts.get('needs_you', 0):,} waiting on you, "
            f"{counts.get('noop', 0):,} already correct"
        )
        self.apply_button.setEnabled(total_ops > 0)
        self.apply_button.setText(f"Apply {total_ops:,} changes" if total_ops else "Apply")

        if plan.notes:
            self.notes.show_message("  ".join(plan.notes), "blue", "info")
        else:
            self.notes.setVisible(False)

        first = self.filter_key if counts.get(self.filter_key) else None
        if first is None:
            for key, _title, _tone in TILES:
                if counts.get(key):
                    first = key
                    break
        self.set_filter(first or "planned")

    def set_plan_cleared(self) -> None:
        """After a run the plan is stale, so say so rather than showing old rows."""
        self.plan = None
        self.model.set_entries([])
        for tile in self.tiles.values():
            tile.set_count(0)
        self.apply_button.setEnabled(False)
        self.apply_button.setText("Apply")
        self.header.set_subtitle("That run is done. Scan again to see the library as it stands now.")
        self.empty.set_text(
            "Run finished",
            "Scan again to see the library as it stands now.",
            "check",
        )
        self.stack.setCurrentWidget(self.empty)
        self.notes.setVisible(False)
        self._refresh_count()

    def set_filter(self, key: str) -> None:
        self.filter_key = key
        for tile_key, tile in self.tiles.items():
            tile.setChecked(tile_key == key)
        bucket = Bucket(key)
        entries = self.plan.by_bucket(bucket) if self.plan else []
        self.model.selectable = bucket in (Bucket.PLANNED, Bucket.JUNK)
        self.model.set_entries(entries)
        self.proxy.sort(0, Qt.AscendingOrder)
        self._refresh_empty()
        self._refresh_count()
        self.resolve_button.setEnabled(bucket in (Bucket.PLANNED, Bucket.NEEDS_YOU, Bucket.DUPLICATE))

    def _refresh_empty(self) -> None:
        if self.plan is None:
            self.empty.set_text(
                "Nothing scanned yet",
                "Choose a folder on the Library screen and press Scan.",
                "film",
            )
            self.stack.setCurrentWidget(self.empty)
            return
        if self.proxy.rowCount() == 0:
            if self.search.text().strip():
                self.empty.set_text(
                    "No match",
                    f"Nothing in this list matches {self.search.text().strip()!r}.",
                    "search",
                )
            else:
                glyph, title, body = EMPTY_COPY.get(self.filter_key, ("info", "Nothing here", ""))
                self.empty.set_text(title, body, glyph)
            self.stack.setCurrentWidget(self.empty)
        else:
            self.stack.setCurrentWidget(self.table)

    def _refresh_count(self) -> None:
        shown = self.proxy.rowCount()
        total = self.model.rowCount()
        if self.model.selectable:
            self.count_label.setText(f"{self.model.selected_count():,} of {total:,} ticked")
        elif shown != total:
            self.count_label.setText(f"{shown:,} of {total:,}")
        else:
            self.count_label.setText(f"{total:,} items")

    # ------------------------------------------------------------ interaction

    def _search_changed(self, text: str) -> None:
        self.proxy.set_needle(text)
        self._refresh_empty()
        self._refresh_count()

    def _sort_changed(self, index: int) -> None:
        self.model.sort_key = SORT_KEYS[index]
        self.proxy.invalidate()
        self.proxy.sort(0, Qt.AscendingOrder)

    def _visible_source_rows(self) -> list[int]:
        return [
            self.proxy.mapToSource(self.proxy.index(row, 0)).row()
            for row in range(self.proxy.rowCount())
        ]

    def _set_all(self, value: bool) -> None:
        self.model.set_all(value, self._visible_source_rows())
        self._refresh_count()
        self.window_ref.plan_selection_changed()

    def _toggle_selection(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        for index in rows:
            entry = index.data(ENTRY_ROLE)
            if entry is not None:
                self.proxy.setData(
                    index, Qt.Unchecked if entry.selected else Qt.Checked, Qt.CheckStateRole
                )
        self._refresh_count()
        self.window_ref.plan_selection_changed()

    def current_entry(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return rows[0].data(ENTRY_ROLE)

    def resolve_selected(self) -> None:
        entry = self.current_entry()
        if entry is None:
            self.window_ref.toast("Select a row first", "info", "amber")
            return
        self.window_ref.resolve_entry(entry)

    # ---------------------------------------------------------- context menu

    def _context_menu(self, point) -> None:
        index = self.table.indexAt(point)
        if not index.isValid():
            return
        self.table.selectionModel().select(
            index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows
        )
        entry = index.data(ENTRY_ROLE)
        if entry is None:
            return

        menu = QMenu(self)
        if entry.item is not None:
            menu.addAction(QAction("Resolve this title\tEnter", menu, triggered=self.resolve_selected))
        if self.model.selectable:
            verb = "Exclude from the run" if entry.selected else "Include in the run"
            menu.addAction(QAction(f"{verb}\tSpace", menu, triggered=self._toggle_selection))
        menu.addSeparator()
        menu.addAction(
            QAction("Open the containing folder", menu, triggered=lambda: self._reveal(entry))
        )
        menu.addAction(QAction("Copy the current path", menu, triggered=lambda: self._copy(entry, False)))
        if entry.target_path:
            menu.addAction(QAction("Copy the proposed path", menu, triggered=lambda: self._copy(entry, True)))
        menu.exec(self.table.viewport().mapToGlobal(point))

    def _reveal(self, entry) -> None:
        path = entry.source_path
        if path is None:
            return
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", str(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(Path(path).parent)])
            self.window_ref.toast("Opened the folder", "folder-open")
        except Exception:
            self.window_ref.toast("Could not open that folder", "warning", "red")

    def _copy(self, entry, proposed: bool) -> None:
        path = entry.target_path if proposed else entry.source_path
        if path is None:
            return
        QApplication.clipboard().setText(str(path))
        self.window_ref.toast("Path copied")
