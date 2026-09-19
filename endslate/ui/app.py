"""The Endslate window: Library, Review, Apply, History, Settings."""
from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from endslate import __version__, jellyfin, presets as presets_mod, report
from endslate.cache import Cache
from endslate.config import Config, app_dir, cache_path, load_config
from endslate.journal import list_runs, mark_reverted
from endslate.models import Bucket, Plan
from endslate.planner import Options
from endslate.presets import BUILTIN_PRESETS, Preset, build_tokens, render
from endslate.ui.dialogs import ResolveDialog
from endslate.ui.resolver import Resolver
from endslate.ui.tablemodel import PlanTableModel
from endslate.ui.workers import ApplyJob, PlanJob, ScanJob, UndoJob

TAB_ORDER = [Bucket.PLANNED, Bucket.NEEDS_YOU, Bucket.DUPLICATE, Bucket.JUNK, Bucket.SKIPPED, Bucket.NOOP]
TAB_LABEL = {
    Bucket.PLANNED: "Planned",
    Bucket.NEEDS_YOU: "Needs you",
    Bucket.DUPLICATE: "Duplicates",
    Bucket.JUNK: "Junk",
    Bucket.SKIPPED: "Skipped",
    Bucket.NOOP: "Already correct",
}


def _table(model: PlanTableModel) -> QTableView:
    view = QTableView()
    view.setModel(model)
    view.setSelectionBehavior(QAbstractItemView.SelectRows)
    view.setAlternatingRowColors(True)
    view.verticalHeader().setVisible(False)
    view.setWordWrap(False)
    header = view.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.Fixed)
    view.setColumnWidth(0, 28)
    header.setSectionResizeMode(1, QHeaderView.Stretch)
    header.setSectionResizeMode(2, QHeaderView.Stretch)
    header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
    return view


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config: Config = load_config()
        self.scan_result = None
        self.plan: Optional[Plan] = None
        self.overrides: dict[str, dict] = {}
        self.show_overrides: dict[str, dict] = {}
        self.job = None

        self.setWindowTitle(f"Endslate {__version__}")
        self.resize(1280, 800)
        self._build()
        self._load_config_into_ui()

    # ------------------------------------------------------------------ layout

    def _build(self) -> None:
        central = QWidget()
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)

        self.sidebar = QListWidget()
        self.sidebar.addItems(["Library", "Review", "Apply", "History", "Settings"])
        self.sidebar.setFixedWidth(150)
        self.sidebar.currentRowChanged.connect(self._go)
        outer.addWidget(self.sidebar)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._library_page())
        self.pages.addWidget(self._review_page())
        self.pages.addWidget(self._apply_page())
        self.pages.addWidget(self._history_page())
        self.pages.addWidget(self._settings_page())
        outer.addWidget(self.pages, 1)

        self.setCentralWidget(central)
        self.sidebar.setCurrentRow(0)

        self.progress = QProgressBar()
        self.progress.setMaximumWidth(220)
        self.progress.setVisible(False)
        self.status = QLabel("")
        self.statusBar().addPermanentWidget(self.status)
        self.statusBar().addPermanentWidget(self.progress)

    def _go(self, row: int) -> None:
        if row == 3:
            self._refresh_history()
        if row == 2:
            self._refresh_apply()
        self.pages.setCurrentIndex(row)

    # ----------------------------------------------------------------- library

    def _library_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("Library")
        font = title.font()
        font.setPointSize(font.pointSize() + 5)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        layout.addWidget(QLabel("Point Endslate at the folder holding your Movies and TV folders."))

        row = QHBoxLayout()
        self.root_edit = QLineEdit()
        self.root_edit.setPlaceholderText(r"M:\Media")
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse)
        row.addWidget(self.root_edit, 1)
        row.addWidget(browse)
        layout.addLayout(row)

        box = QGroupBox("Naming")
        form = QFormLayout(box)
        self.preset_combo = QComboBox()
        self.preset_combo.currentIndexChanged.connect(self._preset_changed)
        form.addRow("Preset", self.preset_combo)
        self.preset_note = QLabel("")
        self.preset_note.setWordWrap(True)
        form.addRow("", self.preset_note)
        self.folder_per_movie = QCheckBox("Give every movie its own folder")
        self.english_only = QCheckBox("Keep English subtitles only, quarantine the rest")
        self.rename_roots = QCheckBox("Rename the top-level folders to match the preset")
        self.quarantine_junk = QCheckBox("Sweep junk into _Quarantine")
        for widget in (self.folder_per_movie, self.english_only, self.rename_roots, self.quarantine_junk):
            form.addRow("", widget)
        layout.addWidget(box)

        self.example = QLabel("")
        self.example.setTextFormat(Qt.RichText)
        self.example.setWordWrap(True)
        layout.addWidget(self.example)

        buttons = QHBoxLayout()
        self.scan_button = QPushButton("Scan")
        self.scan_button.setDefault(True)
        self.scan_button.clicked.connect(self.start_scan)
        buttons.addStretch(1)
        buttons.addWidget(self.scan_button)
        layout.addLayout(buttons)

        self.scan_summary = QLabel("")
        self.scan_summary.setWordWrap(True)
        layout.addWidget(self.scan_summary)
        layout.addStretch(1)
        return page

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose the library folder", self.root_edit.text() or str(Path.home()))
        if chosen:
            self.root_edit.setText(chosen)

    def _preset_changed(self) -> None:
        preset = self.current_preset()
        self.preset_note.setText(preset.description)
        self.folder_per_movie.setChecked(preset.folder_per_movie)
        tokens = build_tokens(title="Fight Club", year=1999)
        episode = build_tokens(title="The 100", year=2014, season=1, episode=4, episode_title="Murphy's Law")
        movie_dir = render(preset.movie_folder, tokens) + "\\" if preset.folder_per_movie else ""
        self.example.setText(
            "<b>Movies</b><br><code>{}\\{}{}.mkv</code><br><br><b>Shows</b><br><code>{}\\{}\\{}\\{}.mkv</code>".format(
                preset.movies_dir, movie_dir, render(preset.movie_file, tokens),
                preset.shows_dir, render(preset.movie_folder, episode),
                render(preset.season_folder, episode), render(preset.episode_file, episode),
            )
        )

    # ------------------------------------------------------------------ review

    def _review_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.review_summary = QLabel("Nothing scanned yet.")
        layout.addWidget(self.review_summary)

        self.tabs = QTabWidget()
        self.models: dict[Bucket, PlanTableModel] = {}
        self.views: dict[Bucket, QTableView] = {}
        for bucket in TAB_ORDER:
            model = PlanTableModel(Path("."), selectable=bucket in (Bucket.PLANNED, Bucket.JUNK))
            view = _table(model)
            view.doubleClicked.connect(self._resolve_current)
            self.models[bucket] = model
            self.views[bucket] = view
            self.tabs.addTab(view, TAB_LABEL[bucket])
        layout.addWidget(self.tabs, 1)

        self.notes_box = QLabel("")
        self.notes_box.setWordWrap(True)
        layout.addWidget(self.notes_box)

        row = QHBoxLayout()
        for label, handler in (("Select all", lambda: self._set_all(True)), ("Select none", lambda: self._set_all(False))):
            button = QPushButton(label)
            button.clicked.connect(handler)
            row.addWidget(button)
        resolve = QPushButton("Resolve selected...")
        resolve.clicked.connect(self._resolve_current)
        row.addWidget(resolve)
        row.addStretch(1)
        forward = QPushButton("Continue to Apply")
        forward.clicked.connect(lambda: self.sidebar.setCurrentRow(2))
        row.addWidget(forward)
        layout.addLayout(row)
        return page

    def _set_all(self, value: bool) -> None:
        bucket = TAB_ORDER[self.tabs.currentIndex()]
        self.models[bucket].set_all(value)

    def _resolve_current(self) -> None:
        bucket = TAB_ORDER[self.tabs.currentIndex()]
        view = self.views[bucket]
        rows = view.selectionModel().selectedRows() if view.selectionModel() else []
        if not rows:
            QMessageBox.information(self, "Pick a row", "Select the row you want to resolve.")
            return
        entry = self.models[bucket].entry_at(rows[0].row())
        if entry is None or entry.item is None:
            QMessageBox.information(self, "Nothing to resolve", "That row is a file operation, not a title.")
            return
        dialog = ResolveDialog(entry.item, matcher=self._tmdb(), parent=self)
        if dialog.exec() != ResolveDialog.Accepted or dialog.result_meta is None:
            return
        if dialog.apply_to_show:
            self.show_overrides[entry.item.show_hint] = dialog.result_meta
        else:
            self.overrides[str(entry.item.video.path)] = dialog.result_meta
        self.start_plan()

    # ------------------------------------------------------------------- apply

    def _apply_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.apply_summary = QLabel("Scan first.")
        self.apply_summary.setWordWrap(True)
        layout.addWidget(self.apply_summary)

        self.jellyfin_warning = QLabel("")
        self.jellyfin_warning.setWordWrap(True)
        self.jellyfin_warning.setStyleSheet("color: #b05c00;")
        layout.addWidget(self.jellyfin_warning)

        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.start_apply)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.apply_button)
        layout.addLayout(row)

        self.apply_log = QPlainTextEdit()
        self.apply_log.setReadOnly(True)
        self.apply_log.setFont(QFont("Consolas" if sys.platform == "win32" else "monospace"))
        layout.addWidget(self.apply_log, 1)
        return page

    def _refresh_apply(self) -> None:
        if self.plan is None:
            self.apply_summary.setText("Scan first.")
            self.apply_button.setEnabled(False)
            return
        operations = self.plan.selected_operations()
        moves = sum(1 for op in operations if op.kind.value in ("move", "quarantine"))
        counts = self.plan.counts()
        self.apply_summary.setText(
            f"<b>{moves} file operations</b> from {counts['planned']} planned items "
            f"and {counts['junk']} junk items.<br>"
            f"{counts['needs_you']} items are unresolved and will not be touched."
        )
        self.apply_button.setEnabled(moves > 0)
        if self.config.check_jellyfin:
            running, how = jellyfin.is_running(self.config.jellyfin_url)
            self.jellyfin_warning.setText(
                f"Jellyfin looks like it is running ({how}). Stop it before applying, or its database "
                "will be scanning files while they move." if running else ""
            )
        else:
            self.jellyfin_warning.setText("")

    # ----------------------------------------------------------------- history

    def _history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Every run is journalled. Undo replays it backwards, skipping anything that moved since."))
        self.history_table = QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels(["Run", "Started", "Operations", "State"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.history_table, 1)

        row = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh_history)
        undo = QPushButton("Undo selected run")
        undo.clicked.connect(self.start_undo)
        open_folder = QPushButton("Open journal folder")
        open_folder.clicked.connect(lambda: QMessageBox.information(self, "Journals", str(app_dir() / "runs")))
        row.addWidget(refresh)
        row.addWidget(undo)
        row.addWidget(open_folder)
        row.addStretch(1)
        layout.addLayout(row)
        return page

    def _refresh_history(self) -> None:
        runs = list_runs()
        self.history_table.setRowCount(len(runs))
        for index, info in enumerate(runs):
            state = "reverted" if info.reverted else ("complete" if info.closed else "interrupted")
            for column, value in enumerate([info.run_id, info.started, str(info.operations), state]):
                self.history_table.setItem(index, column, QTableWidgetItem(value))
        self._runs = runs

    # ---------------------------------------------------------------- settings

    def _settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        metadata = QGroupBox("Metadata")
        form = QFormLayout(metadata)
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.Password)
        self.api_key.setPlaceholderText("TMDB API key (v3 auth)")
        show = QCheckBox("Show")
        show.toggled.connect(lambda on: self.api_key.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
        key_row = QHBoxLayout()
        key_row.addWidget(self.api_key, 1)
        key_row.addWidget(show)
        test = QPushButton("Test")
        test.clicked.connect(self._test_key)
        key_row.addWidget(test)
        key_widget = QWidget()
        key_widget.setLayout(key_row)
        form.addRow("TMDB key", key_widget)

        self.metadata_language = QLineEdit()
        form.addRow("Metadata language", self.metadata_language)
        self.subtitle_language = QLineEdit()
        form.addRow("Subtitle language to keep", self.subtitle_language)
        self.fuzzy = QDoubleSpinBox()
        self.fuzzy.setRange(0.5, 1.0)
        self.fuzzy.setSingleStep(0.01)
        form.addRow("Fuzzy match threshold", self.fuzzy)
        cache_row = QHBoxLayout()
        self.cache_label = QLabel("")
        clear = QPushButton("Clear cache")
        clear.clicked.connect(self._clear_cache)
        cache_row.addWidget(self.cache_label, 1)
        cache_row.addWidget(clear)
        cache_widget = QWidget()
        cache_widget.setLayout(cache_row)
        form.addRow("Cache", cache_widget)
        layout.addWidget(metadata)

        server = QGroupBox("Media server")
        server_form = QFormLayout(server)
        self.check_jellyfin = QCheckBox("Warn me when Jellyfin looks like it is running")
        server_form.addRow("", self.check_jellyfin)
        self.jellyfin_url = QLineEdit()
        server_form.addRow("Jellyfin URL", self.jellyfin_url)
        layout.addWidget(server)

        advanced = QGroupBox("Advanced: the preset's templates")
        advanced_layout = QVBoxLayout(advanced)
        advanced_layout.addWidget(QLabel("Edit the templates, watch the preview, then save it as a preset of your own."))
        template_form = QFormLayout()
        self.t_movies_dir = QLineEdit()
        self.t_shows_dir = QLineEdit()
        self.t_movie_folder = QLineEdit()
        self.t_movie_file = QLineEdit()
        self.t_season_folder = QLineEdit()
        self.t_episode_file = QLineEdit()
        for label, widget in (
            ("Movies folder", self.t_movies_dir),
            ("Shows folder", self.t_shows_dir),
            ("Movie folder", self.t_movie_folder),
            ("Movie file", self.t_movie_file),
            ("Season folder", self.t_season_folder),
            ("Episode file", self.t_episode_file),
        ):
            widget.textChanged.connect(self._preview_templates)
            template_form.addRow(label, widget)
        advanced_layout.addLayout(template_form)

        self.template_preview = QPlainTextEdit()
        self.template_preview.setReadOnly(True)
        self.template_preview.setFixedHeight(120)
        self.template_preview.setFont(QFont("Consolas" if sys.platform == "win32" else "monospace"))
        advanced_layout.addWidget(self.template_preview)

        tokens = QLabel("Tokens: " + ", ".join(f"{{{k}}}" for k in presets_mod.TOKEN_HELP))
        tokens.setWordWrap(True)
        advanced_layout.addWidget(tokens)

        save_row = QHBoxLayout()
        self.new_preset_name = QLineEdit()
        self.new_preset_name.setPlaceholderText("Name for your preset")
        save_preset = QPushButton("Save as preset")
        save_preset.clicked.connect(self._save_preset)
        save_row.addWidget(self.new_preset_name, 1)
        save_row.addWidget(save_preset)
        advanced_layout.addLayout(save_row)
        layout.addWidget(advanced)

        save = QPushButton("Save settings")
        save.clicked.connect(self._save_config)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(save)
        layout.addLayout(row)
        layout.addStretch(1)
        return page

    def _preview_templates(self) -> None:
        preset = self._preset_from_fields("preview")
        movie = build_tokens(title="Fight Club", year=1999)
        episode = build_tokens(title="The 100", year=2014, season=1, episode=4, episode_title="Murphy's Law")
        lines = [
            f"{preset.movies_dir}\\{render(preset.movie_folder, movie)}\\{render(preset.movie_file, movie)}.mkv",
            f"{preset.movies_dir}\\{render(preset.movie_folder, build_tokens(title='Rush Hour'))}\\"
            f"{render(preset.movie_file, build_tokens(title='Rush Hour'))}.mkv",
            f"{preset.shows_dir}\\{render(preset.movie_folder, episode)}\\{render(preset.season_folder, episode)}\\"
            f"{render(preset.episode_file, episode)}.mkv",
        ]
        self.template_preview.setPlainText("\n".join(lines))

    def _preset_from_fields(self, name: str) -> Preset:
        base = self.current_preset()
        return Preset(
            name=name,
            description="Custom",
            movies_dir=self.t_movies_dir.text() or base.movies_dir,
            shows_dir=self.t_shows_dir.text() or base.shows_dir,
            movie_folder=self.t_movie_folder.text() or base.movie_folder,
            movie_file=self.t_movie_file.text() or base.movie_file,
            season_folder=self.t_season_folder.text() or base.season_folder,
            episode_file=self.t_episode_file.text() or base.episode_file,
            folder_per_movie=self.folder_per_movie.isChecked(),
            builtin=False,
        )

    def _save_preset(self) -> None:
        name = self.new_preset_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Name it", "Give the preset a name first.")
            return
        preset = self._preset_from_fields(name)
        self.config.custom_presets = [p for p in self.config.custom_presets if p.get("name") != name]
        self.config.custom_presets.append(preset.to_dict())
        self.config.save()
        self._reload_presets(select=name)
        QMessageBox.information(self, "Saved", f"Preset {name!r} is now in the list.")

    def _test_key(self) -> None:
        from endslate.matcher import TmdbError, TmdbMatcher

        key = self.api_key.text().strip()
        if not key:
            QMessageBox.warning(self, "No key", "Paste your TMDB key first.")
            return
        try:
            matcher = TmdbMatcher(key, cache=Cache(cache_path()))
            results = matcher.search_movie("Fight Club", 1999)
        except TmdbError as exc:
            QMessageBox.critical(self, "TMDB", str(exc))
            return
        if results:
            QMessageBox.information(self, "TMDB", f"Key works. Found {results[0].label}.")
        else:
            QMessageBox.warning(self, "TMDB", f"No results came back. {matcher.offline_reason or 'Check the key and the network.'}")

    def _clear_cache(self) -> None:
        cache = Cache(cache_path())
        cache.clear()
        self._refresh_cache_label()
        QMessageBox.information(self, "Cache", "Metadata cache emptied.")

    def _refresh_cache_label(self) -> None:
        try:
            self.cache_label.setText(f"{Cache(cache_path()).count()} entries in {cache_path()}")
        except Exception:
            self.cache_label.setText(str(cache_path()))

    # ------------------------------------------------------------------ config

    def _reload_presets(self, select: Optional[str] = None) -> None:
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self._presets = list(BUILTIN_PRESETS) + [Preset.from_dict(p) for p in self.config.custom_presets]
        self.preset_combo.addItems([p.name for p in self._presets])
        wanted = select or self.config.preset
        index = next((i for i, p in enumerate(self._presets) if p.name == wanted), 0)
        self.preset_combo.setCurrentIndex(index)
        self.preset_combo.blockSignals(False)
        self._preset_changed()

    def current_preset(self) -> Preset:
        index = max(self.preset_combo.currentIndex(), 0)
        preset = self._presets[index] if index < len(self._presets) else BUILTIN_PRESETS[0]
        return Preset(**preset.to_dict())

    def _load_config_into_ui(self) -> None:
        self._reload_presets()
        self.root_edit.setText(self.config.last_root)
        self.english_only.setChecked(self.config.english_only_subtitles)
        self.rename_roots.setChecked(self.config.rename_top_level_folders)
        self.quarantine_junk.setChecked(self.config.quarantine_junk)
        if self.config.folder_per_movie is not None:
            self.folder_per_movie.setChecked(self.config.folder_per_movie)
        self.api_key.setText(self.config.tmdb_api_key)
        self.metadata_language.setText(self.config.metadata_language)
        self.subtitle_language.setText(self.config.subtitle_language)
        self.fuzzy.setValue(self.config.fuzzy_threshold)
        self.check_jellyfin.setChecked(self.config.check_jellyfin)
        self.jellyfin_url.setText(self.config.jellyfin_url)
        preset = self.current_preset()
        self.t_movies_dir.setText(preset.movies_dir)
        self.t_shows_dir.setText(preset.shows_dir)
        self.t_movie_folder.setText(preset.movie_folder)
        self.t_movie_file.setText(preset.movie_file)
        self.t_season_folder.setText(preset.season_folder)
        self.t_episode_file.setText(preset.episode_file)
        self._refresh_cache_label()
        self._preview_templates()

    def _save_config(self) -> None:
        self.config.tmdb_api_key = self.api_key.text().strip()
        self.config.metadata_language = self.metadata_language.text().strip() or "en-US"
        self.config.subtitle_language = self.subtitle_language.text().strip() or "en"
        self.config.fuzzy_threshold = self.fuzzy.value()
        self.config.check_jellyfin = self.check_jellyfin.isChecked()
        self.config.jellyfin_url = self.jellyfin_url.text().strip() or "http://localhost:8096"
        self.config.preset = self.current_preset().name
        self.config.last_root = self.root_edit.text().strip()
        self.config.english_only_subtitles = self.english_only.isChecked()
        self.config.rename_top_level_folders = self.rename_roots.isChecked()
        self.config.quarantine_junk = self.quarantine_junk.isChecked()
        self.config.folder_per_movie = self.folder_per_movie.isChecked()
        self.config.save()
        self.statusBar().showMessage(f"Settings saved to {app_dir()}", 5000)

    # -------------------------------------------------------------------- jobs

    def _tmdb(self):
        key = self.api_key.text().strip() or self.config.tmdb_api_key
        if not key:
            return None
        from endslate.matcher import TmdbMatcher

        return TmdbMatcher(key, language=self.metadata_language.text().strip() or "en-US",
                           fuzzy_threshold=self.fuzzy.value(), cache=Cache(cache_path()))

    def _options(self) -> Options:
        return Options(
            english_only_subtitles=self.english_only.isChecked(),
            quarantine_junk=self.quarantine_junk.isChecked(),
            rename_top_level_folders=self.rename_roots.isChecked(),
            folder_per_movie=self.folder_per_movie.isChecked(),
            subtitle_language=self.subtitle_language.text().strip() or "en",
        )

    def _busy(self, on: bool, label: str = "") -> None:
        self.progress.setVisible(on)
        self.scan_button.setEnabled(not on)
        self.apply_button.setEnabled(not on and self.plan is not None)
        self.status.setText(label)
        if on:
            self.progress.setRange(0, 0)

    def _on_progress(self, stage: str, done: int, total: int) -> None:
        self.status.setText(f"{stage} {done}/{total}" if total else stage)
        if total:
            self.progress.setRange(0, total)
            self.progress.setValue(done)

    def _on_failure(self, message: str) -> None:
        self._busy(False)
        QMessageBox.critical(self, "Something went wrong", message)

    def start_scan(self) -> None:
        root = Path(self.root_edit.text().strip()).expanduser()
        if not root.is_dir():
            QMessageBox.warning(self, "Not a folder", f"{root} is not a folder.")
            return
        self.config.last_root = str(root)
        self.config.save()
        self._busy(True, "scanning")
        self.job = ScanJob(root)
        self.job.progress.connect(self._on_progress)
        self.job.failed.connect(self._on_failure)
        self.job.done.connect(self._scan_done)
        self.job.start()

    def _scan_done(self, scan_result) -> None:
        self.scan_result = scan_result
        videos = sum(1 for f in scan_result.files if f.kind.value == "video")
        subs = sum(1 for f in scan_result.files if f.kind.value == "subtitle")
        self.scan_summary.setText(
            f"{len(scan_result.files)} files, {videos} videos, {subs} subtitles, "
            f"{scan_result.total_bytes / 1_000_000_000:.1f} GB."
        )
        self.start_plan()

    def start_plan(self) -> None:
        if self.scan_result is None:
            return
        self._busy(True, "planning")
        resolver = Resolver(self._tmdb(), self.overrides, self.show_overrides)
        self.job = PlanJob(self.scan_result, self.current_preset(), self._options(), matcher=resolver)
        self.job.progress.connect(self._on_progress)
        self.job.failed.connect(self._on_failure)
        self.job.done.connect(self._plan_done)
        self.job.start()

    def _plan_done(self, plan: Plan) -> None:
        previous = {}
        if self.plan is not None:
            previous = {str(e.source_path): e.selected for e in self.plan.entries if e.source_path}
        for entry in plan.entries:
            key = str(entry.source_path)
            if key in previous:
                entry.selected = previous[key]
        self.plan = plan
        counts = plan.counts()
        for bucket in TAB_ORDER:
            entries = plan.by_bucket(bucket)
            self.models[bucket].root = plan.root
            self.models[bucket].set_entries(entries)
            self.tabs.setTabText(TAB_ORDER.index(bucket), f"{TAB_LABEL[bucket]} ({len(entries)})")
        self.review_summary.setText(report.summary(plan))
        self.notes_box.setText("\n".join(plan.notes))
        self._busy(False, "")
        self.sidebar.setCurrentRow(1)

    def start_apply(self) -> None:
        if self.plan is None:
            return
        operations = self.plan.selected_operations()
        if not operations:
            QMessageBox.information(self, "Nothing selected", "No operations are ticked.")
            return
        if self.config.check_jellyfin:
            running, how = jellyfin.is_running(self.config.jellyfin_url)
            if running:
                answer = QMessageBox.question(
                    self, "Jellyfin is running",
                    f"{how}.\n\nMoving files while Jellyfin scans can confuse its database.\n\nApply anyway?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
                )
                if answer != QMessageBox.Yes:
                    return
        moves = sum(1 for op in operations if op.kind.value in ("move", "quarantine"))
        answer = QMessageBox.question(
            self, "Apply",
            f"{moves} files will be renamed or moved in {self.plan.root}.\n"
            "Everything is journalled and can be undone.\n\nGo ahead?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self._busy(True, "applying")
        run_id = _dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        self.job = ApplyJob(self.plan, run_id)
        self.job.progress.connect(self._on_progress)
        self.job.failed.connect(self._on_failure)
        self.job.done.connect(self._apply_done)
        self.job.start()

    def _apply_done(self, result) -> None:
        self._busy(False, "")
        lines = []
        if result.failures:
            lines.append(f"{len(result.failures)} FILES DID NOT MOVE")
            lines += [f"  ! {failure.path}: {failure.message}" for failure in result.failures]
            lines.append("")
        lines += [
            f"moved {result.moved} files",
            f"quarantined {result.quarantined}",
            f"created {result.folders_created} folders",
            f"removed {result.folders_removed} empty folders",
            f"{result.bytes_moved / 1_000_000_000:.1f} GB touched",
            f"journal: {result.journal_path}",
        ]
        if result.report_path:
            lines.append(f"problems: {result.report_path}")
        self.apply_log.setPlainText("\n".join(lines))
        self.scan_result = None
        self.plan = None
        self.apply_button.setEnabled(False)

        if result.failures:
            self.apply_summary.setText(
                f"<b style='color:#b00'>{len(result.failures)} files did not move.</b> "
                "The list is below and in the problems file. Everything else went through."
            )
            detail = "\n".join(f"{f.path}\n    {f.message}" for f in result.failures[:15])
            if len(result.failures) > 15:
                detail += f"\n\n...and {len(result.failures) - 15} more."
            box = QMessageBox(QMessageBox.Warning, "Some files did not move",
                              f"Moved {result.moved} files, but {len(result.failures)} did not.", parent=self)
            box.setDetailedText(detail)
            box.exec()
        else:
            self.apply_summary.setText("Run finished with no problems. Scan again to see the library as it stands now.")
            QMessageBox.information(self, "Done", f"Moved {result.moved} files with no problems.")

    def start_undo(self) -> None:
        rows = self.history_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Pick a run", "Select the run you want to reverse.")
            return
        info = self._runs[rows[0].row()]
        answer = QMessageBox.question(
            self, "Undo",
            f"Reverse run {info.run_id}? {info.operations} operations will be replayed backwards.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self._busy(True, "undoing")
        self._undo_info = info
        self.job = UndoJob(info.path)
        self.job.progress.connect(self._on_progress)
        self.job.failed.connect(self._on_failure)
        self.job.done.connect(self._undo_done)
        self.job.start()

    def _undo_done(self, result) -> None:
        self._busy(False, "")
        mark_reverted(self._undo_info.path)
        self._refresh_history()
        message = f"Restored {result.moved} files."
        if result.failures:
            message += "\n\n" + "\n".join(f"{f.path}: {f.message}" for f in result.failures[:15])
        QMessageBox.information(self, "Undo finished", message)


def _log_path() -> Path:
    return app_dir() / "endslate.log"


def _record_crash(text: str) -> Path:
    path = _log_path()
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"\n===== {_dt.datetime.now():%Y-%m-%d %H:%M:%S} =====\n{text}\n")
    except OSError:
        pass
    return path


def _install_crash_handler(app) -> None:
    """Launched from a shortcut there is no console, so an error would vanish."""
    import traceback

    def hook(kind, value, tb):
        text = "".join(traceback.format_exception(kind, value, tb))
        path = _record_crash(text)
        try:
            box = QMessageBox(QMessageBox.Critical, "Endslate hit a problem", str(value))
            box.setInformativeText(f"The details are in {path}")
            box.setDetailedText(text)
            box.exec()
        except Exception:
            pass

    sys.excepthook = hook


def run_app() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Endslate")
    icon_file = Path(__file__).resolve().parent.parent.parent / "assets" / "endslate.ico"
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))
    _install_crash_handler(app)
    try:
        window = MainWindow()
    except Exception as exc:
        import traceback

        path = _record_crash(traceback.format_exc())
        QMessageBox.critical(None, "Endslate could not start", f"{exc}\n\nDetails in {path}")
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_app())
