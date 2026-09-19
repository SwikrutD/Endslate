"""Past runs, each one reversible."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from endslate.journal import RunInfo
from endslate.ui import theme
from endslate.ui.pages.base import Page
from endslate.ui.theme import SPACE
from endslate.ui.widgets import Card, EmptyState, PageHeader, Pill, button, label

STATE_TONE = {"complete": "green", "reverted": "neutral", "interrupted": "amber"}


class RunCard(Card):
    def __init__(self, info: RunInfo, on_undo, parent=None):
        super().__init__(padding=SPACE["lg"], parent=parent)
        self.info = info
        self.body.setSpacing(SPACE["sm"])

        top = QHBoxLayout()
        top.setSpacing(SPACE["md"])
        title = label(info.started.replace("T", "  ") or info.run_id, "subtitle")
        top.addWidget(title)
        state = "reverted" if info.reverted else ("complete" if info.closed else "interrupted")
        self.pill = Pill(state, STATE_TONE.get(state, "neutral"))
        top.addWidget(self.pill)
        top.addStretch(1)

        self.undo = button("Undo this run", "default", "undo", lambda: on_undo(info))
        self.undo.setEnabled(not info.reverted)
        top.addWidget(self.undo)
        self.add_layout(top)

        detail = label(
            f"{info.operations:,} operations  ·  {info.preset or 'unknown preset'}  ·  {info.root}",
            "caption",
        )
        self.add(detail)


class HistoryPage(Page):
    def __init__(self, window, parent=None):
        super().__init__(window, parent=parent)

        self.header = PageHeader(
            "History",
            "Every run is journalled. Undo replays it backwards and skips anything that moved since.",
        )
        self.header.add_action(button("Refresh", "default", "refresh", window.refresh_history))
        self.add(self.header)

        self.list_holder = QWidget()
        self.list_layout = QVBoxLayout(self.list_holder)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(SPACE["md"])

        self.empty = EmptyState(
            "history",
            "No runs yet",
            "Once you apply a plan it appears here, with an Undo button next to it.",
        )

        self.stack = QStackedWidget()
        self.stack.addWidget(self.list_holder)
        self.stack.addWidget(self.empty)
        self.stack.setCurrentWidget(self.empty)
        self.add(self.stack)
        self.add_stretch()

    def set_runs(self, runs: list[RunInfo], on_undo) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for info in runs:
            self.list_layout.addWidget(RunCard(info, on_undo))
        self.stack.setCurrentWidget(self.list_holder if runs else self.empty)
        self.header.set_subtitle(
            f"{len(runs)} run{'s' if len(runs) != 1 else ''} recorded. Undo replays one backwards, "
            "skipping anything that moved since."
            if runs
            else "Every run is journalled and can be reversed."
        )
