"""The review table: current path on the left, proposed path on the right."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from endslate.models import Bucket, OpKind, PlanEntry

COLUMNS = ["", "Now", "After", "Why"]

_AMBER = QColor("#8a6d1f")
_GREY = QColor("#7a7a7a")


class PlanTableModel(QAbstractTableModel):
    def __init__(self, root: Path, entries: Optional[list[PlanEntry]] = None, selectable: bool = True):
        super().__init__()
        self.root = root
        self.entries: list[PlanEntry] = entries or []
        self.selectable = selectable

    # ---------------------------------------------------------------- plumbing

    def set_entries(self, entries: list[PlanEntry]) -> None:
        self.beginResetModel()
        self.entries = entries
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.entries)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLUMNS[section]
        return None

    def entry_at(self, row: int) -> Optional[PlanEntry]:
        if 0 <= row < len(self.entries):
            return self.entries[row]
        return None

    # ------------------------------------------------------------------- data

    def _relative(self, path) -> str:
        if path is None:
            return ""
        try:
            return str(Path(path).relative_to(self.root))
        except ValueError:
            return str(path)

    def _extra_count(self, entry: PlanEntry) -> int:
        if entry.item is None:
            return 0
        return sum(1 for op in entry.ops if op.kind is OpKind.MOVE and op.src != entry.item.video.path)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        entry = self.entries[index.row()]
        column = index.column()

        if role == Qt.CheckStateRole and column == 0 and self.selectable:
            return Qt.Checked if entry.selected else Qt.Unchecked

        if role == Qt.DisplayRole:
            if column == 1:
                return self._relative(entry.source_path)
            if column == 2:
                target = self._relative(entry.target_path)
                extra = self._extra_count(entry)
                if extra:
                    target += f"   (+{extra} subtitle{'s' if extra > 1 else ''})"
                return target
            if column == 3:
                return entry.reason

        if role == Qt.ToolTipRole:
            lines = [f"{self._relative(op.src) or '-'}  ->  {self._relative(op.dst) or '-'}" for op in entry.ops]
            return "\n".join(lines) or entry.reason

        if role == Qt.ForegroundRole and entry.bucket in (Bucket.NOOP, Bucket.SKIPPED):
            return _GREY
        if role == Qt.ForegroundRole and entry.reason and entry.bucket is Bucket.PLANNED:
            return _AMBER
        return None

    def setData(self, index, value, role=Qt.EditRole) -> bool:
        if role == Qt.CheckStateRole and index.column() == 0 and self.selectable:
            self.entries[index.row()].selected = Qt.CheckState(value) == Qt.Checked
            self.dataChanged.emit(index, index, [Qt.CheckStateRole])
            return True
        return False

    def flags(self, index):
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.column() == 0 and self.selectable:
            base |= Qt.ItemIsUserCheckable
        return base

    # ---------------------------------------------------------------- helpers

    def set_all(self, selected: bool) -> None:
        if not self.selectable or not self.entries:
            return
        for entry in self.entries:
            entry.selected = selected
        self.dataChanged.emit(self.index(0, 0), self.index(len(self.entries) - 1, 0), [Qt.CheckStateRole])
