"""The review table's model: one row per reviewable change, one compound column.

A rename is a before and an after, so a row is drawn as two lines rather than
spread across columns. Sorting and searching are handled by the proxy below.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt

from endslate.models import Bucket, OpKind, PlanEntry

ENTRY_ROLE = Qt.UserRole + 1
SORT_ROLE = Qt.UserRole + 2
SEARCH_ROLE = Qt.UserRole + 3

SORT_KEYS = ["Name", "Size", "Folder", "Order found"]


class PlanTableModel(QAbstractTableModel):
    def __init__(self, root: Path = Path("."), selectable: bool = True):
        super().__init__()
        self.root = root
        self.entries: list[PlanEntry] = []
        self.selectable = selectable
        self.sort_key = "Order found"

    # ---------------------------------------------------------------- plumbing

    def set_entries(self, entries: list[PlanEntry]) -> None:
        self.beginResetModel()
        self.entries = entries
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.entries)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 1

    def entry_at(self, row: int) -> Optional[PlanEntry]:
        if 0 <= row < len(self.entries):
            return self.entries[row]
        return None

    def relative(self, path) -> str:
        if path is None:
            return ""
        try:
            return str(Path(path).relative_to(self.root))
        except ValueError:
            return str(path)

    # ------------------------------------------------------------------- data

    def _size_of(self, entry: PlanEntry) -> int:
        if entry.item is not None:
            return entry.item.video.size
        return sum(op.size for op in entry.ops)

    def _search_text(self, entry: PlanEntry) -> str:
        parts = [self.relative(entry.source_path), self.relative(entry.target_path), entry.reason]
        if entry.item is not None:
            parts.append(entry.item.title)
        return " ".join(p for p in parts if p).lower()

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        entry = self.entries[index.row()]

        if role == ENTRY_ROLE:
            return entry
        if role == SEARCH_ROLE:
            return self._search_text(entry)
        if role == SORT_ROLE:
            if self.sort_key == "Size":
                return -self._size_of(entry)
            if self.sort_key == "Folder":
                return self.relative(entry.source_path).lower()
            if self.sort_key == "Name":
                target = entry.target_path or entry.source_path
                return Path(str(target)).name.lower() if target else ""
            return index.row()
        if role == Qt.CheckStateRole and self.selectable:
            return Qt.Checked if entry.selected else Qt.Unchecked
        if role == Qt.DisplayRole:
            return self.relative(entry.target_path) or self.relative(entry.source_path)
        if role == Qt.ToolTipRole:
            lines = []
            for op in entry.ops:
                source = self.relative(op.src) or "-"
                target = self.relative(op.dst) or "-"
                lines.append(f"{op.kind.value}: {source}  →  {target}")
            return "\n".join(lines) or entry.reason
        return None

    def setData(self, index, value, role=Qt.EditRole) -> bool:
        if role == Qt.CheckStateRole and self.selectable:
            self.entries[index.row()].selected = Qt.CheckState(value) == Qt.Checked
            self.dataChanged.emit(index, index, [Qt.CheckStateRole])
            return True
        return False

    def flags(self, index):
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if self.selectable:
            base |= Qt.ItemIsUserCheckable
        return base

    # ---------------------------------------------------------------- helpers

    def set_all(self, selected: bool, rows: Optional[list[int]] = None) -> None:
        if not self.selectable or not self.entries:
            return
        targets = rows if rows is not None else range(len(self.entries))
        for row in targets:
            if 0 <= row < len(self.entries):
                self.entries[row].selected = selected
        self.dataChanged.emit(
            self.index(0, 0), self.index(len(self.entries) - 1, 0), [Qt.CheckStateRole]
        )

    def selected_count(self) -> int:
        return sum(1 for entry in self.entries if entry.selected)

    def extra_moves(self, entry: PlanEntry) -> int:
        if entry.item is None:
            return 0
        return sum(1 for op in entry.ops if op.kind is OpKind.MOVE and op.src != entry.item.video.path)

    def size_of(self, entry: PlanEntry) -> int:
        return self._size_of(entry)


class PlanFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFilterRole(SEARCH_ROLE)
        self.setSortRole(SORT_ROLE)
        self.needle = ""

    def set_needle(self, text: str) -> None:
        if hasattr(self, "beginFilterChange"):  # Qt 6.10 and later
            self.beginFilterChange()
            self.needle = text.strip().lower()
            self.endFilterChange(QSortFilterProxyModel.Direction.Rows)
            return
        self.needle = text.strip().lower()
        if hasattr(self, "invalidateRowsFilter"):
            self.invalidateRowsFilter()
        else:  # pragma: no cover - older Qt
            self.invalidateFilter()

    def filterAcceptsRow(self, row, parent) -> bool:  # noqa: N802
        if not self.needle:
            return True
        index = self.sourceModel().index(row, 0, parent)
        haystack = self.sourceModel().data(index, SEARCH_ROLE) or ""
        return all(word in haystack for word in self.needle.split())
