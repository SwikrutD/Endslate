"""Background jobs, so the window never freezes on a 700 GB library."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, QThread, Signal

from endslate.executor import execute, undo
from endslate.journal import Journal
from endslate.models import Plan
from endslate.planner import Options, build_plan
from endslate.presets import Preset
from endslate.scanner import LibraryScan, scan


class _Job(QThread):
    progress = Signal(str, int, int)
    failed = Signal(str)

    def _emit(self, stage: str, done: int, total: int) -> None:
        self.progress.emit(stage, done, total)


class ScanJob(_Job):
    done = Signal(object)

    def __init__(self, root: Path):
        super().__init__()
        self.root = root

    def run(self) -> None:
        try:
            self._emit("scanning", 0, 0)
            self.done.emit(scan(self.root))
        except Exception as exc:
            self.failed.emit(str(exc))


class PlanJob(_Job):
    done = Signal(object)

    def __init__(self, scan_result: LibraryScan, preset: Preset, options: Options, matcher: Optional[Callable] = None):
        super().__init__()
        self.scan_result = scan_result
        self.preset = preset
        self.options = options
        self.matcher = matcher

    def run(self) -> None:
        try:
            matcher = None
            if self.matcher is not None:
                def matcher(items, _inner=self.matcher):
                    _inner(items, progress=self._emit)
            plan = build_plan(self.scan_result, self.preset, self.options,
                              matcher=matcher, progress=self._emit)
            self.done.emit(plan)
        except Exception as exc:
            self.failed.emit(str(exc))


class HealthJob(_Job):
    done = Signal(object)

    def __init__(self, scan_result: LibraryScan):
        super().__init__()
        self.scan_result = scan_result

    def run(self) -> None:
        try:
            from endslate.health import inspect

            self.done.emit(inspect(self.scan_result, progress=self._emit))
        except Exception as exc:
            self.failed.emit(str(exc))


class ProbeJob(_Job):
    done = Signal(object)

    def __init__(self, paths):
        super().__init__()
        self.paths = list(paths)

    def run(self) -> None:
        try:
            from endslate.health import probe

            self.done.emit(probe(self.paths))
        except Exception as exc:
            self.failed.emit(str(exc))


class ApplyJob(_Job):
    done = Signal(object)

    def __init__(self, plan: Plan, run_id: str):
        super().__init__()
        self.plan = plan
        self.run_id = run_id

    def run(self) -> None:
        try:
            self.done.emit(execute(self.plan, self.run_id, progress=self._emit))
        except Exception as exc:
            self.failed.emit(str(exc))


class UndoJob(_Job):
    done = Signal(object)

    def __init__(self, journal_path: Path):
        super().__init__()
        self.journal_path = journal_path

    def run(self) -> None:
        try:
            self.done.emit(undo(self.journal_path, progress=self._emit))
        except Exception as exc:
            self.failed.emit(str(exc))
