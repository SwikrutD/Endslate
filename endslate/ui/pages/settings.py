"""Keys, appearance, the media server check, and the raw naming templates."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QWidget,
)

from endslate import presets as presets_mod
from endslate.presets import Preset
from endslate.ui.pages.base import Page
from endslate.ui.theme import SPACE
from endslate.ui.widgets import (
    Card,
    Divider,
    ElidedLabel,
    PageHeader,
    ToggleRow,
    button,
    label,
    well,
)

THEME_CHOICES = [("system", "System", "monitor"), ("dark", "Dark", "moon"), ("light", "Light", "sun")]

TEMPLATE_FIELDS = (
    ("movies_dir", "Movies folder"),
    ("shows_dir", "Shows folder"),
    ("anime_dir", "Anime folder"),
    ("movie_folder", "Movie and show folder"),
    ("anime_folder", "Anime show folder"),
    ("movie_file", "Movie file"),
    ("season_folder", "Season folder"),
    ("episode_file", "Episode file"),
)


class Segmented(QWidget):
    """Three keys, one held down: a choice too small to deserve a dropdown."""

    def __init__(self, choices, on_change, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE["md"])
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
        from endslate.ui.widgets import tint_button

        for item in self.buttons.values():
            tint_button(item)


def _secret_row(placeholder: str, test_label: str, on_test):
    """A masked key, a Show toggle and a Test button."""
    row = QHBoxLayout()
    row.setSpacing(SPACE["md"])
    field = QLineEdit()
    field.setEchoMode(QLineEdit.Password)
    field.setPlaceholderText(placeholder)
    well(field)
    row.addWidget(field, 1)
    reveal = button("Show", "ghost", "eye")
    reveal.setCheckable(True)
    reveal.toggled.connect(lambda on: field.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
    row.addWidget(reveal)
    row.addWidget(button(test_label, "default", "key", on_test))
    return row, field, reveal


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
        metadata.add(label("TMDB key", "strong"))
        key_row, self.api_key, self.reveal = _secret_row(
            "TMDB API key, the v3 one from your account settings", "Test the key", window.test_api_key
        )
        metadata.add_layout(key_row)
        metadata.add(
            label(
                "Films and western shows. Without a key Endslate still runs, but anything with no "
                "year in its filename waits in Needs you instead of resolving itself.",
                "caption",
            )
        )
        metadata.add(Divider())

        metadata.add(label("TheTVDB key", "strong"))
        tvdb_row, self.tvdb_key, self.tvdb_reveal = _secret_row(
            "TheTVDB v4 API key, from thetvdb.com/dashboard/account/apikey", "Test the key",
            window.test_tvdb_key,
        )
        metadata.add_layout(tvdb_row)
        pin_form = QFormLayout()
        pin_form.setHorizontalSpacing(SPACE["xl"])
        self.tvdb_pin = QLineEdit()
        self.tvdb_pin.setPlaceholderText("only for a user-supported key")
        self.tvdb_pin.setMaximumWidth(260)
        well(self.tvdb_pin)
        pin_form.addRow(label("Subscriber PIN", "body", wrap=False), self.tvdb_pin)
        metadata.add_layout(pin_form)
        metadata.add(
            label(
                "Anime. Fansub releases number episodes from the start of the show "
                "(\"[SubsPlease] One Piece - 1085\"), and TheTVDB is what turns that into a season "
                "and an episode. Without a key those wait in Needs you.",
                "caption",
            )
        )
        metadata.add(Divider())

        form = QFormLayout()
        form.setHorizontalSpacing(SPACE["xl"])
        form.setVerticalSpacing(SPACE["lg"])
        self.metadata_language = QLineEdit()
        self.metadata_language.setMaximumWidth(170)
        well(self.metadata_language)
        form.addRow(label("Language for titles", "body", wrap=False), self.metadata_language)
        self.subtitle_language = QLineEdit()
        self.subtitle_language.setMaximumWidth(170)
        well(self.subtitle_language)
        form.addRow(label("Subtitle language to keep", "body", wrap=False), self.subtitle_language)
        self.fuzzy = QDoubleSpinBox()
        self.fuzzy.setRange(0.5, 1.0)
        self.fuzzy.setSingleStep(0.01)
        self.fuzzy.setMaximumWidth(170)
        well(self.fuzzy)
        form.addRow(label("Match confidence needed", "body", wrap=False), self.fuzzy)
        metadata.add_layout(form)
        metadata.add(Divider())

        cache_row = QHBoxLayout()
        self.cache_label = ElidedLabel("", "caption")
        cache_row.addWidget(self.cache_label, 1)
        cache_row.addWidget(button("Empty the cache", "ghost", "trash", window.clear_cache))
        metadata.add_layout(cache_row)

        decisions_row = QHBoxLayout()
        self.decisions_label = ElidedLabel("", "caption")
        decisions_row.addWidget(self.decisions_label, 1)
        decisions_row.addWidget(button("Forget them", "ghost", "undo", window.forget_decisions))
        metadata.add_layout(decisions_row)
        metadata.add(
            label(
                "Every title you resolve by hand is remembered, against that file and against "
                "its name, so it never returns to Needs you.",
                "caption",
            )
        )
        self.add(metadata)

        # -------------------------------------------------------- appearance
        self.add(label("Appearance", "section"))
        appearance = Card()
        appearance.add(label("Theme", "strong"))
        self.theme_choice = Segmented(THEME_CHOICES, window.set_theme)
        appearance.add(self.theme_choice)
        appearance.add(label("System follows whatever Windows is set to.", "caption"))
        self.add(appearance)

        # ------------------------------------------------------ media server
        self.add(label("Media server", "section"))
        server = Card()
        self.check_jellyfin = ToggleRow(
            "Warn me when Jellyfin looks like it is running",
            "Moving files while Jellyfin scans can leave it pointing at paths that no longer exist.",
        )
        server.add(self.check_jellyfin)
        server.add(Divider())
        url_form = QFormLayout()
        url_form.setHorizontalSpacing(SPACE["xl"])
        self.jellyfin_url = QLineEdit()
        self.jellyfin_url.setMaximumWidth(340)
        well(self.jellyfin_url)
        url_form.addRow(label("Jellyfin address", "body", wrap=False), self.jellyfin_url)
        server.add_layout(url_form)

        server.add(label("API key", "strong"))
        jf_row, self.jellyfin_key, self.jellyfin_reveal = _secret_row(
            "Jellyfin API key, from Dashboard, API Keys", "Test the connection", window.test_jellyfin
        )
        server.add_layout(jf_row)
        server.add(
            label(
                "With a key Endslate can tell Jellyfin to rescan when a run finishes, and then ask "
                "which films and shows it still could not identify.",
                "caption",
            )
        )
        server.add(Divider())
        self.refresh_after_apply = ToggleRow(
            "Tell Jellyfin to rescan after every run",
            "Needs the API key above.",
        )
        server.add(self.refresh_after_apply)
        self.add(server)

        # ----------------------------------------------------------- advanced
        self.add(label("Advanced: naming templates", "section"))
        advanced = Card()
        advanced.add(
            label(
                "Each preset is a set of templates. Edit them, watch the preview, then save the "
                "result under a name of your own and it joins the list on the Library screen.",
                "muted",
            )
        )
        template_form = QFormLayout()
        template_form.setHorizontalSpacing(SPACE["xl"])
        template_form.setVerticalSpacing(SPACE["md"])
        self.fields: dict[str, QLineEdit] = {}
        for key, title in TEMPLATE_FIELDS:
            field = QLineEdit()
            field.setProperty("role", "template")
            well(field)
            field.textChanged.connect(window.preview_templates)
            template_form.addRow(label(title, "body", wrap=False), field)
            self.fields[key] = field
        advanced.add_layout(template_form)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setProperty("role", "code")
        well(self.preview, radius=20)
        self.preview.setFixedHeight(124)
        advanced.add(self.preview)

        tokens = label("Tokens: " + "  ".join(f"{{{k}}}" for k in presets_mod.TOKEN_HELP), "caption")
        advanced.add(tokens)

        save_row = QHBoxLayout()
        save_row.setSpacing(SPACE["md"])
        self.new_preset_name = QLineEdit()
        self.new_preset_name.setPlaceholderText("Name for your preset")
        well(self.new_preset_name)
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
