"""Keys, appearance, the media server check, and the raw naming templates."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from endslate import presets as presets_mod
from endslate.presets import Preset, build_tokens, render
from endslate.ui import theme
from endslate.ui.pages.base import Page
from endslate.ui.theme import RADIUS_SM, SPACE
from endslate.ui.widgets import Card, Divider, PageHeader, button, label

THEME_CHOICES = [("system", "System", "monitor"), ("dark", "Dark", "moon"), ("light", "Light", "sun")]


class Segmented(QWidget):
    """Three mutually exclusive buttons, for a choice too small to deserve a dropdown."""

    def __init__(self, choices, on_change, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE["xs"])
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}
        for key, title, icon_name in choices:
            item = button(title, "default", icon_name)
            item.setCheckable(True)
            item.clicked.connect(lambda _=False, k=key: on_change(k))
            self.group.addButton(item)
            layout.addWidget(item)
            self.buttons[key] = item
        layout.addStretch(1)

    def select(self, key: str) -> None:
        for item_key, item in self.buttons.items():
            item.setChecked(item_key == key)

    def restyle(self) -> None:
        palette = theme.active()
        for item in self.buttons.values():
            if item.isChecked():
                item.setStyleSheet(
                    f"QPushButton {{ background: {palette.accent_soft}; color: {palette.text};"
                    f" border: 1px solid {palette.accent}; border-radius: {RADIUS_SM}px; padding: 7px 14px; }}"
                )
            else:
                item.setStyleSheet("")


class SettingsPage(Page):
    def __init__(self, window, parent=None):
        super().__init__(window, parent=parent)

        self.header = PageHeader(
            "Settings",
            "Stored in %LOCALAPPDATA%\\Endslate, never inside your media folder.",
        )
        self.save_button = button("Save settings", "primary", "check", window.save_settings)
        self.header.add_action(self.save_button)
        self.add(self.header)

        # ---------------------------------------------------------- metadata
        self.add(label("Metadata", "section"))
        metadata = Card()
        key_row = QHBoxLayout()
        key_row.setSpacing(SPACE["sm"])
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.Password)
        self.api_key.setPlaceholderText("TMDB API key, the v3 one from your account settings")
        key_row.addWidget(self.api_key, 1)
        self.reveal = button("Show", "ghost")
        self.reveal.setCheckable(True)
        self.reveal.toggled.connect(
            lambda on: self.api_key.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password)
        )
        key_row.addWidget(self.reveal)
        key_row.addWidget(button("Test the key", "default", "key", window.test_api_key))
        metadata.add(label("TMDB key", "body"))
        metadata.add_layout(key_row)
        metadata.add(
            label(
                "Without a key Endslate still runs, but anything with no year in its filename waits "
                "in Needs you instead of resolving itself.",
                "caption",
            )
        )
        metadata.add(Divider())

        form = QFormLayout()
        form.setHorizontalSpacing(SPACE["xl"])
        form.setVerticalSpacing(SPACE["md"])
        self.metadata_language = QLineEdit()
        self.metadata_language.setMaximumWidth(150)
        form.addRow(label("Language for titles", "body"), self.metadata_language)
        self.subtitle_language = QLineEdit()
        self.subtitle_language.setMaximumWidth(150)
        form.addRow(label("Subtitle language to keep", "body"), self.subtitle_language)
        self.fuzzy = QDoubleSpinBox()
        self.fuzzy.setRange(0.5, 1.0)
        self.fuzzy.setSingleStep(0.01)
        self.fuzzy.setMaximumWidth(150)
        form.addRow(label("Match confidence needed", "body"), self.fuzzy)
        metadata.add_layout(form)
        metadata.add(Divider())

        cache_row = QHBoxLayout()
        self.cache_label = label("", "caption")
        cache_row.addWidget(self.cache_label, 1)
        cache_row.addWidget(button("Empty the cache", "ghost", "trash", window.clear_cache))
        metadata.add_layout(cache_row)
        self.add(metadata)

        # -------------------------------------------------------- appearance
        self.add(label("Appearance", "section"))
        appearance = Card()
        appearance.add(label("Theme", "body"))
        self.theme_choice = Segmented(THEME_CHOICES, window.set_theme)
        appearance.add(self.theme_choice)
        appearance.add(label("System follows whatever Windows is set to.", "caption"))
        self.add(appearance)

        # ------------------------------------------------------ media server
        self.add(label("Media server", "section"))
        server = Card()
        self.check_jellyfin = QCheckBox("Warn me when Jellyfin looks like it is running")
        server.add(self.check_jellyfin)
        server.add(
            label(
                "Moving files while Jellyfin is scanning can leave its database pointing at paths "
                "that no longer exist.",
                "caption",
            )
        )
        url_form = QFormLayout()
        self.jellyfin_url = QLineEdit()
        self.jellyfin_url.setMaximumWidth(320)
        url_form.addRow(label("Jellyfin address", "body"), self.jellyfin_url)
        server.add_layout(url_form)
        self.add(server)

        # ----------------------------------------------------------- advanced
        self.add(label("Advanced: naming templates", "section"))
        advanced = Card()
        advanced.add(
            label(
                "Each preset is four templates. Edit them, watch the preview, then save the result "
                "under a name of your own and it joins the list on the Library screen.",
                "muted",
            )
        )
        template_form = QFormLayout()
        template_form.setHorizontalSpacing(SPACE["xl"])
        template_form.setVerticalSpacing(SPACE["sm"])
        self.fields: dict[str, QLineEdit] = {}
        for key, title in (
            ("movies_dir", "Movies folder"),
            ("shows_dir", "Shows folder"),
            ("movie_folder", "Movie folder"),
            ("movie_file", "Movie file"),
            ("season_folder", "Season folder"),
            ("episode_file", "Episode file"),
        ):
            field = QLineEdit()
            field.setProperty("role", "template")
            field.textChanged.connect(window.preview_templates)
            template_form.addRow(label(title, "body"), field)
            self.fields[key] = field
        advanced.add_layout(template_form)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setProperty("role", "code")
        self.preview.setFixedHeight(96)
        advanced.add(self.preview)

        tokens = label("Tokens: " + "  ".join(f"{{{k}}}" for k in presets_mod.TOKEN_HELP), "caption")
        advanced.add(tokens)

        save_row = QHBoxLayout()
        save_row.setSpacing(SPACE["sm"])
        self.new_preset_name = QLineEdit()
        self.new_preset_name.setPlaceholderText("Name for your preset")
        save_row.addWidget(self.new_preset_name, 1)
        save_row.addWidget(button("Save as a preset", "default", "sparkle", window.save_preset))
        advanced.add_layout(save_row)
        self.add(advanced)
        self.add_stretch()

    # ------------------------------------------------------------------ state

    def templates(self) -> dict[str, str]:
        return {key: field.text() for key, field in self.fields.items()}

    def set_templates(self, preset: Preset) -> None:
        for key, field in self.fields.items():
            field.blockSignals(True)
            field.setText(getattr(preset, key))
            field.blockSignals(False)

    def set_preview(self, lines: list[str]) -> None:
        self.preview.setPlainText("\n".join(lines))
