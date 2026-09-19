"""Confirm, run, and read the result."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from endslate.ui import theme
from endslate.ui.delegate import human_size
from endslate.ui.pages.base import Page
from endslate.ui.theme import RADIUS_MD, SPACE
from endslate.ui import icons
from endslate.ui.widgets import Banner, Card, Divider, PageHeader, button, label


class Metric(QWidget):
    """One number and what it counts."""

    def __init__(self, caption: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.value = label("0", "metric", wrap=False)
        self.caption = label(caption, "caption", wrap=False)
        self.setMinimumWidth(150)
        layout.addWidget(self.value)
        layout.addWidget(self.caption)

    def set_value(self, text: str) -> None:
        self.value.setText(text)


class Promise(QWidget):
    """One line of the safety contract, stated at the moment it matters."""

    def __init__(self, icon_name: str, title: str, detail: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, SPACE["xs"], 0, SPACE["xs"])
        layout.setSpacing(SPACE["md"])
        self.glyph = QLabel()
        self.glyph.setFixedSize(18, 18)
        self.icon_name = icon_name
        layout.addWidget(self.glyph, 0, Qt.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(1)
        text.addWidget(label(title, "body", wrap=False))
        text.addWidget(label(detail, "caption"))
        layout.addLayout(text, 1)
        self.restyle()

    def restyle(self) -> None:
        self.glyph.setPixmap(icons.pixmap(self.icon_name, theme.active().green, 18))


class ApplyPage(Page):
    def __init__(self, window, parent=None):
        super().__init__(window, parent=parent)

        self.header = PageHeader("Apply", "Scan a library first.")
        self.add(self.header)

        self.jellyfin = Banner("amber", "warning", "")
        self.jellyfin.setVisible(False)
        self.add(self.jellyfin)

        summary = Card()
        metrics = QHBoxLayout()
        metrics.setSpacing(SPACE["2xl"])
        self.metric_renames = Metric("renamed or moved")
        self.metric_quarantine = Metric("sent to _Quarantine")
        self.metric_folders = Metric("folders created")
        self.metric_bytes = Metric("of video touched")
        for metric in (self.metric_renames, self.metric_quarantine, self.metric_folders, self.metric_bytes):
            metrics.addWidget(metric)
        metrics.addStretch(1)
        summary.add_layout(metrics)
        summary.add(Divider())
        summary.add(
            label(
                "Files are renamed where they sit. Nothing is deleted, nothing is overwritten, and "
                "every operation is written to a journal you can reverse from the History screen.",
                "muted",
            )
        )

        actions = QHBoxLayout()
        actions.setSpacing(SPACE["md"])
        self.unresolved = label("", "caption")
        actions.addWidget(self.unresolved, 1)
        self.apply_button = button("Apply", "primary", "play", window.start_apply)
        self.apply_button.setEnabled(False)
        actions.addWidget(self.apply_button)
        summary.add_layout(actions)
        self.add(summary)

        promises = Card()
        promises.add(label("Before you commit", "section"))
        promises.add(
            Promise(
                "check",
                "Nothing is deleted",
                "Junk and unwanted subtitles move to _Quarantine and sit there until you empty it.",
            )
        )
        promises.add(Divider())
        promises.add(
            Promise(
                "check",
                "Nothing is overwritten",
                "If a target name is already taken, that one operation stops and is reported.",
            )
        )
        promises.add(Divider())
        promises.add(
            Promise(
                "check",
                "Every run is reversible",
                "Each operation is journalled as it happens. History replays a run backwards.",
            )
        )
        promises.add(Divider())
        promises.add(
            Promise(
                "check",
                "Unresolved items are left alone",
                "Anything Endslate is not confident about stays exactly where it is.",
            )
        )
        self.add(promises)

        self.progress_card = Card(quiet=True, padding=SPACE["lg"])
        self.progress_label = label("Working", "muted")
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress_card.add(self.progress_label)
        self.progress_card.add(self.progress)
        self.progress_card.setVisible(False)
        self.add(self.progress_card)

        self.result = Banner("green", "check", "")
        self.result.setVisible(False)
        self.add(self.result)

        self.log_card = Card(padding=SPACE["lg"])
        self.log_card.add(label("Run log", "section"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setProperty("role", "code")
        self.log.setMinimumHeight(190)
        self.log_card.add(self.log)
        self.log_card.setVisible(False)
        self.add(self.log_card)
        self.add_stretch()

    # ------------------------------------------------------------------ state

    def set_plan(self, plan, jellyfin_message: str = "") -> None:
        if plan is None:
            self.header.set_subtitle("Scan a library first.")
            self.apply_button.setEnabled(False)
            self.apply_button.setText("Apply")
            for metric in (self.metric_renames, self.metric_quarantine, self.metric_folders, self.metric_bytes):
                metric.set_value("0")
            return

        operations = plan.selected_operations()
        renames = sum(1 for op in operations if op.kind.value == "move")
        quarantine = sum(1 for op in operations if op.kind.value == "quarantine")
        folders = sum(1 for op in operations if op.kind.value == "mkdir")
        size = sum(op.size for op in operations)

        self.metric_renames.set_value(f"{renames:,}")
        self.metric_quarantine.set_value(f"{quarantine:,}")
        self.metric_folders.set_value(f"{folders:,}")
        self.metric_bytes.set_value(human_size(size) or "0")

        counts = plan.counts()
        self.header.set_subtitle(f"{plan.root}")
        waiting = counts.get("needs_you", 0) + counts.get("duplicate", 0)
        self.unresolved.setText(
            f"{waiting:,} items are unresolved and will be left exactly where they are."
            if waiting else "Everything in the plan is resolved."
        )
        total = renames + quarantine
        self.apply_button.setEnabled(total > 0)
        self.apply_button.setText(f"Apply {total:,} changes" if total else "Nothing to apply")

        if jellyfin_message:
            self.jellyfin.show_message(jellyfin_message, "amber", "warning")
        else:
            self.jellyfin.setVisible(False)

    def set_busy(self, busy: bool, message: str = "") -> None:
        self.progress_card.setVisible(busy)
        self.apply_button.setEnabled(not busy and self.apply_button.text() != "Nothing to apply")
        if message:
            self.progress_label.setText(message)

    def set_progress(self, stage: str, done: int, total: int) -> None:
        self.progress_label.setText(f"{stage.capitalize()} {done:,} of {total:,}" if total else stage.capitalize())
        if total:
            self.progress.setRange(0, total)
            self.progress.setValue(done)
        else:
            self.progress.setRange(0, 0)

    def show_result(self, result) -> None:
        self.set_busy(False)
        self.log_card.setVisible(True)
        lines = []
        if result.failures:
            lines.append(f"{len(result.failures)} FILES DID NOT MOVE")
            lines += [f"  ! {failure.path}: {failure.message}" for failure in result.failures]
            lines.append("")
        lines += [
            f"renamed or moved   {result.moved:,}",
            f"quarantined        {result.quarantined:,}",
            f"folders created    {result.folders_created:,}",
            f"empty folders gone {result.folders_removed:,}",
            f"touched            {human_size(result.bytes_moved) or '0'}",
            f"journal            {result.journal_path}",
        ]
        if result.report_path:
            lines.append(f"problems           {result.report_path}")
        self.log.setPlainText("\n".join(lines))

        if result.failures:
            self.result.show_message(
                f"{len(result.failures)} files did not move. They are listed at the top of the log "
                "and written to the problems file. Everything else went through.",
                "red",
                "warning",
            )
        else:
            self.result.show_message(
                f"Renamed {result.moved:,} files and swept {result.quarantined:,} into _Quarantine, "
                "with no problems. The run can be reversed from History.",
                "green",
                "check",
            )
        self.apply_button.setEnabled(False)
        self.apply_button.setText("Applied")
