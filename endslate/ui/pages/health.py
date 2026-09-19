"""Problems in the library that renaming cannot fix."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from endslate.health import NOTE, PROBLEM, WARNING, Finding, HealthReport
from endslate.ui import icons, theme
from endslate.ui.delegate import human_size
from endslate.ui.pages.base import Page
from endslate.ui.theme import RADIUS_MD, SPACE
from endslate.ui.widgets import Card, EmptyState, PageHeader, Pill, StatTile, button, elide, label

SEVERITY_LABEL = {PROBLEM: "Problems", WARNING: "Worth a look", NOTE: "Notes"}


class FindingCard(Card):
    def __init__(self, finding: Finding, page, parent=None):
        super().__init__(quiet=True, padding=SPACE["lg"], parent=parent)
        self.finding = finding
        self.body.setSpacing(SPACE["sm"])

        head = QHBoxLayout()
        head.setSpacing(SPACE["md"])
        self.glyph = QWidget()
        self.glyph.setFixedSize(9, 9)
        head.addWidget(self.glyph, 0, Qt.AlignTop)
        head.addWidget(label(finding.title, "body"), 1)
        if finding.bytes_involved:
            head.addWidget(Pill(human_size(finding.bytes_involved), finding.tone))
        self.add_layout(head)

        detail = label(finding.detail, "caption")
        self.add(detail)

        if finding.primary is not None:
            actions = QHBoxLayout()
            actions.setSpacing(SPACE["sm"])
            actions.addWidget(button("Open the folder", "ghost", "folder-open", self._reveal))
            actions.addWidget(button("Copy the path", "ghost", "copy", self._copy))
            actions.addStretch(1)
            self.add_layout(actions)

        self.page = page
        self.restyle()

    def restyle(self) -> None:
        palette = theme.active()
        from endslate.ui.theme import tone_colours

        strong, _soft, _text = tone_colours(palette, self.finding.tone)
        self.glyph.setStyleSheet(f"background: {strong}; border-radius: 4px;")

    def _reveal(self) -> None:
        path = self.finding.primary
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", str(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(Path(path).parent)])
        except Exception:
            self.page.window_ref.toast("Could not open that folder", "warning", "red")

    def _copy(self) -> None:
        QApplication.clipboard().setText(str(self.finding.primary))
        self.page.window_ref.toast("Path copied")


class HealthPage(Page):
    def __init__(self, window, parent=None):
        super().__init__(window, parent=parent)

        self.header = PageHeader(
            "Health",
            "Missing episodes, redundant archives, duplicate copies and broken files. Nothing here is renamed.",
        )
        self.header.add_action(button("Check playability", "default", "play", window.check_playability))
        self.header.add_action(button("Run the check", "primary", "sparkle", window.start_health))
        self.add(self.header)

        tiles_holder = QWidget()
        tiles = QHBoxLayout(tiles_holder)
        tiles.setContentsMargins(0, 0, 0, 0)
        tiles.setSpacing(SPACE["sm"])
        self.tiles: dict[str, StatTile] = {}
        for key, title, tone in (
            (PROBLEM, "Problems", "red"),
            (WARNING, "Worth a look", "amber"),
            (NOTE, "Notes", "blue"),
            ("reclaimable", "Reclaimable", "neutral"),
        ):
            tile = StatTile(key, title, tone)
            tile.setCursor(Qt.ArrowCursor)
            tiles.addWidget(tile)
            self.tiles[key] = tile
        self.add(tiles_holder)

        self.list_holder = QWidget()
        self.list_layout = QVBoxLayout(self.list_holder)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(SPACE["md"])

        self.empty = EmptyState(
            "sparkle",
            "Nothing checked yet",
            "Scan a library on the Library screen, then run the check.",
        )
        self.stack = QStackedWidget()
        self.stack.addWidget(self.list_holder)
        self.stack.addWidget(self.empty)
        self.stack.setCurrentWidget(self.empty)
        self.add(self.stack)
        self.add_stretch()
        self.report: HealthReport | None = None

    # ------------------------------------------------------------------ data

    def set_report(self, report: HealthReport) -> None:
        self.report = report
        counts = report.counts()
        for key in (PROBLEM, WARNING, NOTE):
            self.tiles[key].set_count(counts.get(key, 0))
        self.tiles["reclaimable"].value.setText(human_size(report.reclaimable) or "0")

        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for severity in (PROBLEM, WARNING, NOTE):
            findings = report.by_severity(severity)
            if not findings:
                continue
            self.list_layout.addWidget(label(SEVERITY_LABEL[severity], "section"))
            for finding in findings:
                self.list_layout.addWidget(FindingCard(finding, self))

        self.header.set_subtitle(
            f"{report.videos_checked:,} videos and {report.episodes_checked:,} episodes checked."
        )
        if report.findings:
            self.stack.setCurrentWidget(self.list_holder)
        else:
            self.empty.set_text(
                "Nothing wrong found",
                f"{report.videos_checked:,} videos checked. No gaps in any season, no redundant "
                "archives, no duplicate copies and no broken files.",
                "check",
            )
            self.stack.setCurrentWidget(self.empty)

    def suspect_paths(self) -> list[Path]:
        """The files worth spending ffprobe time on."""
        if self.report is None:
            return []
        out: list[Path] = []
        for finding in self.report.findings:
            if finding.kind in ("tiny_video", "empty_file", "unextracted_archive"):
                out.extend(finding.paths)
        return out
