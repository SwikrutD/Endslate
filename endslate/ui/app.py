"""The Endslate window: a rail, five screens, and the jobs behind them."""
from __future__ import annotations

import base64
import datetime as _dt
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from endslate import __version__, jellyfin, presets as presets_mod
from endslate.cache import Cache
from endslate.config import Config, app_dir, cache_path, load_config
from endslate.journal import list_runs, mark_reverted
from endslate.models import Plan
from endslate.planner import Options
from endslate.presets import BUILTIN_PRESETS, Preset, build_tokens, render
from endslate.ui import icons, theme
from endslate.ui.dialogs import ResolveDialog
from endslate.ui.pages.apply import ApplyPage
from endslate.ui.pages.history import HistoryPage
from endslate.ui.pages.library import LibraryPage
from endslate.ui.pages.review import ReviewPage
from endslate.ui.pages.settings import SettingsPage
from endslate.ui.resolver import Resolver
from endslate.ui.theme import RAIL_WIDTH, SPACE
from endslate.ui.widgets import Toast, label, restyle_tree
from endslate.ui.workers import ApplyJob, PlanJob, ScanJob, UndoJob

NAV = [
    ("Library", "library"),
    ("Review", "review"),
    ("Apply", "apply"),
    ("History", "history"),
    ("Settings", "settings"),
]

ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"


class Rail(QFrame):
    """The left-hand navigation. Icons plus words, because both help."""

    def __init__(self, on_select, parent=None):
        super().__init__(parent)
        self.setObjectName("Rail")
        self.setFixedWidth(RAIL_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["md"], SPACE["xl"], SPACE["md"], SPACE["lg"])
        layout.setSpacing(SPACE["xs"])

        brand = QHBoxLayout()
        brand.setSpacing(SPACE["sm"])
        self.mark = QLabel()
        self.mark.setFixedSize(30, 30)
        icon_file = ASSETS / "endslate.png"
        if icon_file.exists():
            from PySide6.QtGui import QPixmap

            self.mark.setPixmap(
                QPixmap(str(icon_file)).scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        brand.addWidget(self.mark)
        names = QVBoxLayout()
        names.setSpacing(0)
        title = QLabel("Endslate")
        title.setObjectName("RailBrand")
        theme.apply_role_font(title, "title")
        version = QLabel(f"v{__version__}")
        version.setObjectName("RailTag")
        theme.apply_role_font(version, "caption")
        names.addWidget(title)
        names.addWidget(version)
        brand.addLayout(names)
        brand.addStretch(1)
        layout.addLayout(brand)
        layout.addSpacing(SPACE["xl"])

        self.buttons: dict[str, QPushButton] = {}
        for index, (title_text, key) in enumerate(NAV):
            item = QPushButton(f"  {title_text}")
            item.setProperty("nav", "true")
            item.setCursor(Qt.PointingHandCursor)
            item.setIconSize(QSize(18, 18))
            item.setShortcut(QKeySequence(f"Ctrl+{index + 1}"))
            item.setToolTip(f"{title_text}  (Ctrl+{index + 1})")
            item.clicked.connect(lambda _=False, k=key: on_select(k))
            layout.addWidget(item)
            self.buttons[key] = item

        layout.addStretch(1)
        self.foot = QLabel("")
        self.foot.setObjectName("RailFoot")
        self.foot.setWordWrap(False)
        self.foot.setMinimumWidth(0)
        self._foot_text = ""
        layout.addWidget(self.foot)

    def select(self, key: str) -> None:
        for item_key, item in self.buttons.items():
            item.setProperty("current", "true" if item_key == key else "false")
            item.style().unpolish(item)
            item.style().polish(item)
        self.restyle()

    def set_foot(self, text: str) -> None:
        from endslate.ui.widgets import elide

        self._foot_text = text
        elide(self.foot, text, Qt.ElideLeft)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        if self._foot_text:
            self.set_foot(self._foot_text)

    def restyle(self) -> None:
        palette = theme.active()
        for key, item in self.buttons.items():
            current = item.property("current") == "true"
            item.setIcon(icons.icon(key, palette.text if current else palette.text_faint, 18))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config: Config = load_config()
        self.scan_result = None
        self.plan: Optional[Plan] = None
        self.overrides: dict[str, dict] = {}
        self.show_overrides: dict[str, dict] = {}
        self.job = None
        self._undo_info = None

        self.setWindowTitle("Endslate")
        self.setMinimumSize(1060, 720)
        icon_file = ASSETS / "endslate.ico"
        if icon_file.exists():
            self.setWindowIcon(QIcon(str(icon_file)))

        self._build()
        self._restore_geometry()
        self._load_config_into_ui()
        self.go_to("library")

    # ------------------------------------------------------------------ build

    def _build(self) -> None:
        central = QWidget()
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.rail = Rail(self.go_to)
        outer.addWidget(self.rail)

        self.pages = QStackedWidget()
        self.library_page = LibraryPage(self)
        self.review_page = ReviewPage(self)
        self.apply_page = ApplyPage(self)
        self.history_page = HistoryPage(self)
        self.settings_page = SettingsPage(self)
        self.page_map = {
            "library": self.library_page,
            "review": self.review_page,
            "apply": self.apply_page,
            "history": self.history_page,
            "settings": self.settings_page,
        }
        for page in self.page_map.values():
            self.pages.addWidget(page)
        outer.addWidget(self.pages, 1)

        self.setCentralWidget(central)
        self.toast_widget = Toast(central)
        self.library_page.scan_button.clicked.connect(self.start_scan)
        QShortcut(QKeySequence("F5"), self, activated=self.start_scan)

        self.statusBar().setSizeGripEnabled(False)
        self.status = QLabel("")
        self.statusBar().addPermanentWidget(self.status)
        self.statusBar().setStyleSheet("QStatusBar { border: none; }")

    # ----------------------------------------------------------- navigation

    def go_to(self, key: str) -> None:
        if key == "history":
            self.refresh_history()
        if key == "apply":
            self.apply_page.set_plan(self.plan, self._jellyfin_message())
        self.rail.select(key)
        self.pages.setCurrentWidget(self.page_map[key])

    def go_to_apply(self) -> None:
        self.go_to("apply")

    def toast(self, text: str, icon_name: str = "check", tone: str = "green") -> None:
        self.toast_widget.show_message(text, icon_name, tone)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self.toast_widget._place()

    # --------------------------------------------------------------- config

    def _presets(self) -> list[Preset]:
        return list(BUILTIN_PRESETS) + [Preset.from_dict(p) for p in self.config.custom_presets]

    def current_preset(self) -> Preset:
        name = self.library_page.current_preset_name()
        for preset in self._presets():
            if preset.name == name:
                data = preset.to_dict()
                data["folder_per_movie"] = self.library_page.folder_per_movie.isChecked()
                return Preset(**data)
        return BUILTIN_PRESETS[0]

    def _load_config_into_ui(self) -> None:
        theme_mode = theme.resolve_mode(self.config.theme)
        theme.apply_theme(QApplication.instance(), theme_mode)

        self.library_page.load_presets(self._presets(), self.config.preset)
        self.library_page.dropzone.set_path(self.config.last_root)
        self.library_page.english_only.setChecked(self.config.english_only_subtitles)
        self.library_page.rename_roots.setChecked(self.config.rename_top_level_folders)
        self.library_page.quarantine_junk.setChecked(self.config.quarantine_junk)
        preset = self.current_preset()
        self.library_page.folder_per_movie.setChecked(
            self.config.folder_per_movie if self.config.folder_per_movie is not None else preset.folder_per_movie
        )

        self.settings_page.api_key.setText(self.config.tmdb_api_key)
        self.settings_page.metadata_language.setText(self.config.metadata_language)
        self.settings_page.subtitle_language.setText(self.config.subtitle_language)
        self.settings_page.fuzzy.setValue(self.config.fuzzy_threshold)
        self.settings_page.check_jellyfin.setChecked(self.config.check_jellyfin)
        self.settings_page.jellyfin_url.setText(self.config.jellyfin_url)
        self.settings_page.theme_choice.select(self.config.theme)
        self.settings_page.set_templates(preset)
        self.rail.set_foot(self.config.last_root or "No folder chosen yet")
        self.refresh_cache_label()
        self.preview_templates()
        restyle_tree(self)

    def save_settings(self) -> None:
        self.config.tmdb_api_key = self.settings_page.api_key.text().strip()
        self.config.metadata_language = self.settings_page.metadata_language.text().strip() or "en-US"
        self.config.subtitle_language = self.settings_page.subtitle_language.text().strip() or "en"
        self.config.fuzzy_threshold = self.settings_page.fuzzy.value()
        self.config.check_jellyfin = self.settings_page.check_jellyfin.isChecked()
        self.config.jellyfin_url = self.settings_page.jellyfin_url.text().strip() or "http://localhost:8096"
        self._save_library_choices()
        self.config.save()
        self.toast("Settings saved")

    def _save_library_choices(self) -> None:
        self.config.preset = self.library_page.current_preset_name()
        self.config.last_root = self.library_page.dropzone.path
        self.config.english_only_subtitles = self.library_page.english_only.isChecked()
        self.config.rename_top_level_folders = self.library_page.rename_roots.isChecked()
        self.config.quarantine_junk = self.library_page.quarantine_junk.isChecked()
        self.config.folder_per_movie = self.library_page.folder_per_movie.isChecked()

    def set_theme(self, mode: str) -> None:
        self.config.theme = mode
        self.config.save()
        theme.apply_theme(QApplication.instance(), theme.resolve_mode(mode))
        self.settings_page.theme_choice.select(mode)
        restyle_tree(self)
        self.rail.restyle()
        self.toast(f"{mode.capitalize()} theme", "sparkle")

    def library_path_changed(self, path: str) -> None:
        self.config.last_root = path
        self.config.save()
        self.rail.set_foot(path)
        self.library_page.set_hint("Ready to scan.")

    def preset_changed(self) -> None:
        self.settings_page.set_templates(self.current_preset())
        self.preview_templates()
        if self.scan_result is not None:
            self.start_plan()

    # ---------------------------------------------------------------- jobs

    def _options(self) -> Options:
        return Options(
            english_only_subtitles=self.library_page.english_only.isChecked(),
            quarantine_junk=self.library_page.quarantine_junk.isChecked(),
            rename_top_level_folders=self.library_page.rename_roots.isChecked(),
            folder_per_movie=self.library_page.folder_per_movie.isChecked(),
            subtitle_language=self.settings_page.subtitle_language.text().strip() or "en",
        )

    def tmdb(self):
        key = self.settings_page.api_key.text().strip() or self.config.tmdb_api_key
        if not key:
            return None
        from endslate.matcher import TmdbMatcher

        return TmdbMatcher(
            key,
            language=self.settings_page.metadata_language.text().strip() or "en-US",
            fuzzy_threshold=self.settings_page.fuzzy.value(),
            cache=Cache(cache_path()),
        )

    def _busy(self, on: bool, message: str = "") -> None:
        self.library_page.scan_button.setEnabled(not on)
        self.library_page.scan_button.setText("Scanning..." if on else "Scan library")
        self.status.setText(message)
        self.apply_page.set_busy(on and self.pages.currentWidget() is self.apply_page, message)

    def _on_progress(self, stage: str, done: int, total: int) -> None:
        self.status.setText(f"{stage} {done:,}/{total:,}" if total else stage)
        self.apply_page.set_progress(stage, done, total)

    def _on_failure(self, message: str) -> None:
        self._busy(False)
        QMessageBox.critical(self, "Something went wrong", message)

    def start_scan(self) -> None:
        path = Path(self.library_page.dropzone.path or "").expanduser()
        if not str(path) or not path.is_dir():
            self.go_to("library")
            self.toast("Choose a folder first", "folder", "amber")
            return
        self._save_library_choices()
        self.config.save()
        self._busy(True, "scanning")
        self.job = ScanJob(path)
        self.job.progress.connect(self._on_progress)
        self.job.failed.connect(self._on_failure)
        self.job.done.connect(self._scan_done)
        self.job.start()

    def _scan_done(self, scan_result) -> None:
        self.scan_result = scan_result
        videos = sum(1 for f in scan_result.files if f.kind.value == "video")
        subs = sum(1 for f in scan_result.files if f.kind.value == "subtitle")
        self.library_page.set_hint(
            f"{len(scan_result.files):,} files  ·  {videos:,} videos  ·  {subs:,} subtitles  ·  "
            f"{scan_result.total_bytes / 1_000_000_000:.1f} GB"
        )
        self.start_plan()

    def start_plan(self) -> None:
        if self.scan_result is None:
            return
        self._busy(True, "planning")
        resolver = Resolver(self.tmdb(), self.overrides, self.show_overrides)
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
        self.review_page.set_plan(plan)
        self.apply_page.set_plan(plan, self._jellyfin_message())
        self._busy(False, "")
        self.go_to("review")

    def plan_selection_changed(self) -> None:
        if self.plan is None:
            return
        total = len(self.plan.selected_operations())
        self.review_page.apply_button.setEnabled(total > 0)
        self.review_page.apply_button.setText(f"Apply {total:,} changes" if total else "Apply")
        self.apply_page.set_plan(self.plan, self._jellyfin_message())

    # --------------------------------------------------------------- resolve

    def resolve_entry(self, entry) -> None:
        if entry.item is None:
            self.toast("That row is a file operation, not a title", "info", "amber")
            return
        dialog = ResolveDialog(entry.item, matcher=self.tmdb(), parent=self)
        if dialog.exec() != ResolveDialog.Accepted or dialog.result_meta is None:
            return
        if dialog.apply_to_show:
            self.show_overrides[entry.item.show_hint] = dialog.result_meta
        else:
            self.overrides[str(entry.item.video.path)] = dialog.result_meta
        self.toast(f"Set to {dialog.result_meta['title']}", "sparkle")
        self.start_plan()

    # ----------------------------------------------------------------- apply

    def _jellyfin_message(self) -> str:
        if not self.config.check_jellyfin:
            return ""
        running, how = jellyfin.is_running(self.config.jellyfin_url)
        if not running:
            return ""
        return (
            f"Jellyfin looks like it is running ({how}). Stop the server before applying, or its "
            "library scan will be reading files while they move."
        )

    def start_apply(self) -> None:
        if self.plan is None:
            return
        operations = self.plan.selected_operations()
        if not operations:
            self.toast("Nothing is ticked", "info", "amber")
            return
        if self._jellyfin_message():
            answer = QMessageBox.question(
                self,
                "Jellyfin is running",
                f"{self._jellyfin_message()}\n\nApply anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        moves = sum(1 for op in operations if op.kind.value in ("move", "quarantine"))
        answer = QMessageBox.question(
            self,
            "Apply",
            f"{moves:,} files will be renamed or moved in {self.plan.root}.\n"
            "Everything is journalled and can be undone from History.\n\nGo ahead?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self._busy(True, "applying")
        self.apply_page.set_busy(True, "Applying")
        run_id = _dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        self.job = ApplyJob(self.plan, run_id)
        self.job.progress.connect(self._on_progress)
        self.job.failed.connect(self._on_failure)
        self.job.done.connect(self._apply_done)
        self.job.start()

    def _apply_done(self, result) -> None:
        self._busy(False, "")
        self.apply_page.show_result(result)
        self.scan_result = None
        self.plan = None
        self.review_page.set_plan_cleared()
        if result.failures:
            self.toast(f"{len(result.failures)} files did not move", "warning", "red")
        else:
            self.toast(f"Renamed {result.moved:,} files", "check")

    # --------------------------------------------------------------- history

    def refresh_history(self) -> None:
        self.runs = list_runs()
        self.history_page.set_runs(self.runs, self.start_undo)

    def start_undo(self, info) -> None:
        answer = QMessageBox.question(
            self,
            "Undo",
            f"Reverse the run from {info.started}?\n\n{info.operations:,} operations will be "
            "replayed backwards. Anything that has moved since is reported, not forced.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
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
        if self._undo_info is not None:
            mark_reverted(self._undo_info.path)
        self.refresh_history()
        if result.failures:
            box = QMessageBox(
                QMessageBox.Warning,
                "Undo finished with problems",
                f"Restored {result.moved:,} files. {len(result.failures)} could not be put back.",
                parent=self,
            )
            box.setDetailedText("\n".join(f"{f.path}\n    {f.message}" for f in result.failures[:20]))
            box.exec()
        else:
            self.toast(f"Restored {result.moved:,} files", "undo")

    # -------------------------------------------------------------- settings

    def test_api_key(self) -> None:
        from endslate.matcher import TmdbError, TmdbMatcher

        key = self.settings_page.api_key.text().strip()
        if not key:
            self.toast("Paste your TMDB key first", "key", "amber")
            return
        try:
            matcher = TmdbMatcher(key, cache=Cache(cache_path()))
            results = matcher.search_movie("Fight Club", 1999)
        except TmdbError as exc:
            QMessageBox.critical(self, "TMDB", str(exc))
            return
        if results:
            self.toast(f"Key works, found {results[0].label}", "check")
        else:
            QMessageBox.warning(
                self,
                "TMDB",
                f"No results came back. {matcher.offline_reason or 'Check the key and the network.'}",
            )

    def clear_cache(self) -> None:
        Cache(cache_path()).clear()
        self.refresh_cache_label()
        self.toast("Metadata cache emptied", "trash")

    def refresh_cache_label(self) -> None:
        try:
            self.settings_page.cache_label.setText(
                f"{Cache(cache_path()).count():,} cached lookups in {cache_path()}"
            )
        except Exception:
            self.settings_page.cache_label.setText(str(cache_path()))

    def preview_templates(self) -> None:
        preset = self._preset_from_fields("preview")
        movie = build_tokens(title="Fight Club", year=1999)
        bare = build_tokens(title="Rush Hour")
        episode = build_tokens(title="The 100", year=2014, season=1, episode=4, episode_title="Murphy's Law")
        folder = f"{render(preset.movie_folder, movie)}\\" if preset.folder_per_movie else ""
        self.settings_page.set_preview(
            [
                f"{preset.movies_dir}\\{folder}{render(preset.movie_file, movie)}.mkv",
                f"{preset.movies_dir}\\{render(preset.movie_folder, bare)}\\{render(preset.movie_file, bare)}.mkv"
                if preset.folder_per_movie
                else f"{preset.movies_dir}\\{render(preset.movie_file, bare)}.mkv",
                f"{preset.shows_dir}\\{render(preset.movie_folder, episode)}\\"
                f"{render(preset.season_folder, episode)}\\{render(preset.episode_file, episode)}.mkv",
            ]
        )

    def _preset_from_fields(self, name: str) -> Preset:
        base = self.current_preset()
        values = self.settings_page.templates()
        data = base.to_dict()
        data.update({key: value or data[key] for key, value in values.items()})
        data["name"] = name
        data["description"] = "Custom"
        data["builtin"] = False
        data["folder_per_movie"] = self.library_page.folder_per_movie.isChecked()
        return Preset(**data)

    def save_preset(self) -> None:
        name = self.settings_page.new_preset_name.text().strip()
        if not name:
            self.toast("Give the preset a name first", "info", "amber")
            return
        preset = self._preset_from_fields(name)
        self.config.custom_presets = [p for p in self.config.custom_presets if p.get("name") != name]
        self.config.custom_presets.append(preset.to_dict())
        self.config.preset = name
        self.config.save()
        self.library_page.load_presets(self._presets(), name)
        self.settings_page.new_preset_name.clear()
        self.toast(f"Preset {name!r} saved")

    # ------------------------------------------------------------- geometry

    def _restore_geometry(self) -> None:
        try:
            if self.config.window_geometry:
                self.restoreGeometry(QByteArray(base64.b64decode(self.config.window_geometry)))
            else:
                self.resize(1320, 880)
        except Exception:
            self.resize(1320, 880)

    def closeEvent(self, event):  # noqa: N802
        try:
            self.config.window_geometry = base64.b64encode(bytes(self.saveGeometry())).decode("ascii")
            self._save_library_choices()
            self.config.save()
        except Exception:
            pass
        super().closeEvent(event)


# ------------------------------------------------------------------ bootstrap


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


def _install_crash_handler() -> None:
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
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Endslate")
    app.setApplicationDisplayName("Endslate")
    icon_file = ASSETS / "endslate.ico"
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))
    _install_crash_handler()
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
