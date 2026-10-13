"""Confirm, run, and read the result."""
from __future__ import annotations

import math

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from endslate.ui import icons, neu, theme
from endslate.ui.delegate import human_size
from endslate.ui.pages.base import Page
from endslate.ui.theme import SPACE
from endslate.ui.widgets import (
    Banner,
    Card,
    Divider,
    IconWell,
    PageHeader,
    button,
    label,
    well,
)


class Metric(QWidget):
    """One number and what it counts, read off a pressed-in gauge."""

    def __init__(self, caption: str, parent=None):
        super().__init__(parent)
        neu.style(self, "inset", radius=22, depth="md")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["lg"], SPACE["md"] + 2, SPACE["lg"], SPACE["md"] + 2)
        layout.setSpacing(2)
        self.caption = label(caption, "section", wrap=False)
        self.value = label("0", "metric", wrap=False)
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
        self.well = IconWell(icon_name, size=36, glyph=16, tone="green")
        layout.addWidget(self.well, 0, Qt.AlignVCenter)
        text = QVBoxLayout()
        text.setSpacing(1)
        text.addWidget(label(title, "strong", wrap=False))
        text.addWidget(label(detail, "caption"))
        layout.addLayout(text, 1)

    def restyle(self) -> None:
        self.well.update()


class DialButton(QPushButton):
    """The commit: a round key set in two rings, lit violet when there is work.

    Hover turns the outer ring of ticks half a revolution and swells the key, the
    way a physical dial gives under a thumb. Pressing sinks the key into its well.
    """

    DIAL = 132
    ROOM = 34  # the shadow falls this far outside the dial

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("variant", "primary")
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._hover = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(500)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._set_hover)
        self.setStyleSheet("background: transparent; border: none;")

    def _set_hover(self, value) -> None:
        self._hover = float(value)
        self.update()

    def _go(self, target: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(target)
        self._anim.start()

    def enterEvent(self, event):  # noqa: N802
        if self.isEnabled():
            self._go(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._go(0.0)
        super().leaveEvent(event)

    def sizeHint(self) -> QSize:  # noqa: N802
        metrics = QFontMetrics(theme.font("heading"))
        width = max(self.DIAL + 2 * self.ROOM, metrics.horizontalAdvance(self.text()) + 40)
        return QSize(width, self.ROOM + self.DIAL + SPACE["lg"] + metrics.height() + SPACE["lg"])

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    def setText(self, text: str) -> None:  # noqa: N802
        super().setText(text)
        self.updateGeometry()

    def restyle(self) -> None:
        self.update()

    def paintEvent(self, event):  # noqa: N802
        palette = theme.active()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        enabled = self.isEnabled()
        hover = self._hover if enabled else 0.0
        size = float(self.DIAL)
        centre_x = self.width() / 2
        outer = QRectF(centre_x - size / 2, self.ROOM, size, size)

        neu.paint_raised(painter, outer, size / 2, neu.mix(neu.RAISED["lg"], neu.LIFTED["lg"], hover),
                         strength=1.0 if enabled else 0.5)
        ring = outer.adjusted(14, 14, -14, -14)
        neu.paint_inset(painter, ring, ring.width() / 2, neu.INSET["md"])

        # Ticks around the ring, turning half a revolution on hover.
        painter.save()
        painter.translate(outer.center())
        painter.rotate(180.0 * hover)
        tick = QColor(palette.accent if enabled else palette.text_faint)
        tick.setAlphaF(0.35 + 0.45 * hover if enabled else 0.3)
        painter.setPen(QPen(tick, 2, Qt.SolidLine, Qt.RoundCap))
        for index in range(24):
            angle = index * math.tau / 24
            inner_r, outer_r = size / 2 - 10, size / 2 - 5
            painter.drawLine(
                QPointF(math.cos(angle) * inner_r, math.sin(angle) * inner_r),
                QPointF(math.cos(angle) * outer_r, math.sin(angle) * outer_r),
            )
        painter.restore()

        grow = 1.0 + 0.05 * hover
        key_size = (ring.width() - 22) * grow
        key = QRectF(0, 0, key_size, key_size)
        key.moveCenter(ring.center())
        if self.isDown():
            neu.paint_inset(painter, key, key_size / 2, neu.INSET["md"],
                            fill=neu.accent_fill(key) if enabled else None)
        else:
            neu.paint_raised(painter, key, key_size / 2, neu.RAISED["md"],
                             fill=neu.accent_fill(key) if enabled else None,
                             strength=1.0 if enabled else 0.6)
        glyph = 30
        pixmap = icons.pixmap("play", palette.on_accent if enabled else palette.text_faint, glyph)
        painter.drawPixmap(QPointF(key.center().x() - glyph / 2 + 2, key.center().y() - glyph / 2), pixmap)

        painter.setFont(theme.font("heading"))
        painter.setPen(QColor(palette.text if enabled else palette.text_faint))
        text_rect = QRectF(0, outer.bottom() + SPACE["lg"], self.width(), QFontMetrics(painter.font()).height() + 4)
        painter.drawText(text_rect, Qt.AlignHCenter | Qt.AlignVCenter, self.text())
        if self.hasFocus() and enabled:
            neu.paint_ring(painter, outer, size / 2, palette.accent)
        painter.end()


class ApplyPage(Page):
    def __init__(self, window, parent=None):
        super().__init__(window, parent=parent)

        self.header = PageHeader("Apply", "Scan a library first.")
        self.add(self.header)

        self.jellyfin = Banner("amber", "warning", "")
        self.jellyfin.setVisible(False)
        self.add(self.jellyfin)

        # The commit card: four gauges, and the dial that sets them going.
        summary = Card(padding=SPACE["2xl"])
        summary.setObjectName("Slate")
        top = QHBoxLayout()
        top.setSpacing(SPACE["2xl"])
        gauges = QVBoxLayout()
        gauges.setSpacing(SPACE["lg"])
        row_one = QHBoxLayout()
        row_one.setSpacing(SPACE["lg"])
        row_two = QHBoxLayout()
        row_two.setSpacing(SPACE["lg"])
        self.metric_renames = Metric("renamed or moved")
        self.metric_quarantine = Metric("sent to _Quarantine")
        self.metric_folders = Metric("folders created")
        self.metric_bytes = Metric("of video touched")
        row_one.addWidget(self.metric_renames)
        row_one.addWidget(self.metric_quarantine)
        row_two.addWidget(self.metric_folders)
        row_two.addWidget(self.metric_bytes)
        gauges.addLayout(row_one)
        gauges.addLayout(row_two)
        top.addLayout(gauges, 1)

        dial_column = QVBoxLayout()
        dial_column.setSpacing(SPACE["xs"])
        self.apply_button = DialButton("Apply")
        self.apply_button.clicked.connect(window.start_apply)
        self.apply_button.setEnabled(False)
        dial_column.addWidget(self.apply_button, 0, Qt.AlignHCenter)
        top.addLayout(dial_column)
        summary.add_layout(top)
        summary.add(Divider())
        summary.add(
            label(
                "Files are renamed where they sit. Nothing is deleted, nothing is overwritten, and "
                "every operation is written to a journal you can reverse from the History screen.",
                "muted",
            )
        )
        self.unresolved = label("", "caption")
        summary.add(self.unresolved)
        self.add(summary)

        promises = Card()
        promises.add(label("Before you commit", "section"))
        for index, (title, detail) in enumerate((
            ("Nothing is deleted",
             "Junk and unwanted subtitles move to _Quarantine and sit there until you empty it."),
            ("Nothing is overwritten",
             "If a target name is already taken, that one operation stops and is reported."),
            ("Every run is reversible",
             "Each operation is journalled as it happens. History replays a run backwards."),
            ("Unresolved items are left alone",
             "Anything Endslate is not confident about stays exactly where it is."),
        )):
            if index:
                promises.add(Divider())
            promises.add(Promise("check", title, detail))
        self.add(promises)

        self.progress_card = Card(quiet=True, padding=SPACE["lg"])
        self.progress_label = label("Working", "muted")
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        neu.style(self.progress, "inset", radius=8, depth="sm")
        self.progress.setMinimumHeight(16)
        self.progress_card.add(self.progress_label)
        self.progress_card.add(self.progress)
        self.progress_card.setVisible(False)
        self.add(self.progress_card)

        self.result = Banner("green", "check", "")
        self.result.setVisible(False)
        self.add(self.result)

        self.jellyfin_card = Card(padding=SPACE["xl"])
        self.jellyfin_card.add(label("Does Jellyfin agree?", "section"))
        self.jellyfin_card.add(
            label(
                "Renaming is the means. Whether Jellyfin recognises every film and show is the "
                "result, and only Jellyfin can answer that.",
                "muted",
            )
        )
        jf_actions = QHBoxLayout()
        jf_actions.setSpacing(SPACE["md"])
        self.refresh_button = button("Tell Jellyfin to rescan", "default", "refresh", window.jellyfin_refresh)
        self.report_button = button("Ask what it recognises", "default", "review", window.jellyfin_report)
        jf_actions.addWidget(self.refresh_button)
        jf_actions.addWidget(self.report_button)
        jf_actions.addStretch(1)
        self.jellyfin_card.add_layout(jf_actions)
        self.jellyfin_result = Banner("blue", "info", "")
        self.jellyfin_result.setVisible(False)
        self.jellyfin_card.add(self.jellyfin_result)
        self.unidentified = QPlainTextEdit()
        self.unidentified.setReadOnly(True)
        self.unidentified.setProperty("role", "code")
        well(self.unidentified, radius=20)
        self.unidentified.setFixedHeight(160)
        self.unidentified.setVisible(False)
        self.jellyfin_card.add(self.unidentified)
        self.jellyfin_card.setVisible(False)
        self.add(self.jellyfin_card)

        self.log_card = Card(padding=SPACE["xl"])
        self.log_card.add(label("Run log", "section"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setProperty("role", "code")
        well(self.log, radius=20)
        self.log.setMinimumHeight(200)
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
            self.unresolved.setText("")
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
        self.apply_button.setEnabled(not busy and self.apply_button.text() not in ("Nothing to apply", "Apply", "Applied"))
        if message:
            self.progress_label.setText(message)

    def set_progress(self, stage: str, done: int, total: int) -> None:
        self.progress_label.setText(f"{stage.capitalize()} {done:,} of {total:,}" if total else stage.capitalize())
        if total:
            self.progress.setRange(0, total)
            self.progress.setValue(done)
        else:
            self.progress.setRange(0, 0)

    def show_jellyfin(self, text: str, tone: str = "blue", icon_name: str = "info",
                      detail: str = "") -> None:
        self.jellyfin_card.setVisible(True)
        self.jellyfin_result.show_message(text, tone, icon_name)
        self.unidentified.setPlainText(detail)
        self.unidentified.setVisible(bool(detail))

    def show_result(self, result) -> None:
        self.set_busy(False)
        self.log_card.setVisible(True)
        self.jellyfin_card.setVisible(True)
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

        if result.journal_path is None and result.failures:
            # Preflight refused: nothing moved, and the plan is still there.
            self.result.show_message(
                f"Nothing was moved. {len(result.failures)} problem"
                f"{'s' if len(result.failures) != 1 else ''} turned up before the first file, "
                "listed in the log. Fix them, or untick those rows, and apply again.",
                "red",
                "warning",
            )
            return
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
