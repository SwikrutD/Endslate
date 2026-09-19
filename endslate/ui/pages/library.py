"""Choose the folder and the naming scheme, then scan."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from endslate.presets import BUILTIN_PRESETS, Preset, build_tokens, render
from endslate.ui import icons, theme
from endslate.ui.pages.base import Page
from endslate.ui.theme import RADIUS_LG, SPACE
from endslate.ui.widgets import (
    Card,
    Divider,
    PageHeader,
    PresetCard,
    ToggleRow,
    button,
    label,
)


class Dropzone(QFrame):
    """Where the library folder is chosen. Takes a dropped folder too."""

    chosen = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Dropzone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(112)
        self.path = ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE["xl"], SPACE["lg"], SPACE["xl"], SPACE["lg"])
        layout.setSpacing(SPACE["lg"])

        self.glyph = QLabel()
        self.glyph.setFixedSize(34, 34)
        layout.addWidget(self.glyph, 0, Qt.AlignVCenter)

        text = QVBoxLayout()
        text.setSpacing(2)
        text.setAlignment(Qt.AlignVCenter)
        self.title = label("Choose your media folder", "subtitle", wrap=False)
        self.detail = label("Drop it here, or browse. The folder that holds Movies and TV Shows.", "muted", wrap=False)
        self._detail_text = self.detail.text()
        text.addWidget(self.title)
        text.addWidget(self.detail)
        layout.addLayout(text, 1)

        self.browse = button("Browse", "default", "folder-open", self._browse)
        layout.addWidget(self.browse, 0, Qt.AlignVCenter)
        self.restyle()

    def set_path(self, path: str) -> None:
        self.path = path
        if path:
            self.title.setText(Path(path).name or path)
            self._detail_text = path
            self.detail.setProperty("role", "mono")
            theme.apply_role_font(self.detail, "mono")
            self.browse.setText("Change")
        else:
            self.title.setText("Choose your media folder")
            self._detail_text = "Drop it here, or browse. The folder that holds Movies and TV Shows."
            self.detail.setProperty("role", "muted")
            theme.apply_role_font(self.detail, "muted")
            self.browse.setText("Browse")
        self._elide()
        self.setProperty("chosen", "true" if path else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.restyle()

    def _elide(self) -> None:
        from endslate.ui.widgets import elide

        elide(self.detail, self._detail_text, Qt.ElideMiddle)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._elide()

    def restyle(self) -> None:
        palette = theme.active()
        name = "folder" if not self.path else "film"
        colour = palette.accent if self.path else palette.text_faint
        self.glyph.setPixmap(icons.pixmap(name, colour, 34))
        if self.path:
            self.setStyleSheet(
                f"#Dropzone {{ background: {palette.surface}; border: 1px solid {palette.line};"
                f" border-radius: {RADIUS_LG}px; }}"
            )
        else:
            self.setStyleSheet("")

    def _browse(self) -> None:
        start = self.path or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Choose the library folder", start)
        if chosen:
            self.chosen.emit(chosen)

    # ------------------------------------------------------------ drag & drop

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("hot", "true")
            self.style().unpolish(self)
            self.style().polish(self)

    def dragLeaveEvent(self, event):  # noqa: N802
        self.setProperty("hot", "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event):  # noqa: N802
        self.setProperty("hot", "false")
        self.style().unpolish(self)
        self.style().polish(self)
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_dir():
                self.chosen.emit(str(path))
                return
            if path.parent.is_dir():
                self.chosen.emit(str(path.parent))
                return


class LibraryPage(Page):
    def __init__(self, window, parent=None):
        super().__init__(window, parent=parent)

        self.header = PageHeader(
            "Library", "Pick the folder and the naming scheme. Nothing moves until you approve it."
        )
        self.scan_button = button("Scan library", "primary", "search")
        self.scan_button.setShortcut("Ctrl+R")
        self.scan_button.setToolTip("Scan the library and build a plan  (Ctrl+R)")
        self.header.add_action(self.scan_button)
        self.add(self.header)

        self.dropzone = Dropzone()
        self.dropzone.chosen.connect(self._path_chosen)
        self.add(self.dropzone)

        self.add(label("Naming scheme", "section"))
        grid_holder = QWidget()
        self.grid = QGridLayout(grid_holder)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(SPACE["md"])
        self.preset_cards: list[PresetCard] = []
        self.add(grid_holder)

        self.add(label("Options", "section"))
        options = Card(padding=SPACE["lg"])
        self.folder_per_movie = ToggleRow(
            "Give every movie its own folder",
"Fight Club (1999)\\Fight Club (1999).mkv, rather than a bare file.",
        )
        self.english_only = ToggleRow(
            "Keep English subtitles only",
"Other languages go to _Quarantine. Nothing is deleted.",
        )
        self.rename_roots = ToggleRow(
            "Rename the top-level folders",
"TV Shows becomes Shows. Turn this off to leave the roots alone.",
        )
        self.quarantine_junk = ToggleRow(
            "Sweep junk into _Quarantine",
"Resource forks, release-site adverts, and folders holding no media.",
        )
        for index, row in enumerate(
            (self.folder_per_movie, self.english_only, self.rename_roots, self.quarantine_junk)
        ):
            if index:
                options.add(Divider())
            options.add(row)
        self.add(options)

        self.hint = label("", "caption")
        self.add(self.hint)
        self.add_stretch()

    # ---------------------------------------------------------------- presets

    def load_presets(self, presets: list[Preset], current: str) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.preset_cards = []
        movie = build_tokens(title="Fight Club", year=1999)
        episode = build_tokens(title="Dark", year=2017, season=1, episode=2, episode_title="Lies")
        for index, preset in enumerate(presets):
            movie_line = render(preset.movie_file, movie) + ".mkv"
            if preset.folder_per_movie:
                movie_line = f"{render(preset.movie_folder, movie)}\\{movie_line}"
            example = f"{movie_line}\n{render(preset.episode_file, episode)}.mkv"
            card = PresetCard(preset.name, preset.description, example)
            card.setToolTip(
                f"{preset.movies_dir}\\{render(preset.movie_folder, movie)}\\"
                f"{render(preset.movie_file, movie)}.mkv\n"
                f"{preset.shows_dir}\\{render(preset.movie_folder, episode)}\\"
                f"{render(preset.season_folder, episode)}\\{render(preset.episode_file, episode)}.mkv"
            )
            card.clicked.connect(lambda _=False, name=preset.name: self.select_preset(name))
            self.grid.addWidget(card, index // 2, index % 2)
            self.preset_cards.append(card)
        self.select_preset(current, notify=False)

    def select_preset(self, name: str, notify: bool = True) -> None:
        found = False
        for card in self.preset_cards:
            card.setChecked(card.preset_name == name)
            found = found or card.isChecked()
        if not found and self.preset_cards:
            self.preset_cards[0].setChecked(True)
        if notify:
            self.window_ref.preset_changed()

    def current_preset_name(self) -> str:
        for card in self.preset_cards:
            if card.isChecked():
                return card.preset_name
        return BUILTIN_PRESETS[0].name

    def _path_chosen(self, path: str) -> None:
        self.dropzone.set_path(path)
        self.window_ref.library_path_changed(path)

    def set_hint(self, text: str) -> None:
        self.hint.setText(text)


def preset_extension(preset: Preset) -> str:
    return ".mkv"
