"""The only module that writes. Everything it does is recorded and reversible."""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from endslate.journal import Journal, read_records
from endslate.models import OpKind, Operation, Plan
from endslate.sanitize import MAX_PATH
from endslate.scanner import QUARANTINE_DIRNAME

Progress = Callable[[str, int, int], None]


@dataclass
class Problem:
    path: Optional[Path]
    message: str


@dataclass
class Result:
    moved: int = 0
    folders_created: int = 0
    folders_removed: int = 0
    quarantined: int = 0
    bytes_moved: int = 0
    failures: list[Problem] = field(default_factory=list)
    run_id: str = ""
    journal_path: Optional[Path] = None

    @property
    def ok(self) -> bool:
        return not self.failures


def preflight(plan: Plan, operations: Optional[list[Operation]] = None) -> list[Problem]:
    """Every check that can fail is made before anything moves."""
    operations = plan.selected_operations() if operations is None else operations
    problems: list[Problem] = []
    planned_targets: dict[Path, Path] = {}
    sources = {op.src for op in operations if op.src is not None}

    root = plan.root.resolve()
    if not os.access(root, os.W_OK):
        problems.append(Problem(root, "library root is not writable"))

    for op in operations:
        if op.kind is OpKind.MKDIR:
            continue
        src, dst = op.src, op.dst
        if src is None or dst is None:
            continue
        if not src.exists():
            problems.append(Problem(src, "source has disappeared since the scan"))
            continue
        try:
            dst.resolve().relative_to(root)
        except ValueError:
            problems.append(Problem(dst, "target is outside the library root"))
            continue
        if len(str(dst)) >= MAX_PATH:
            problems.append(Problem(dst, f"target path is {len(str(dst))} characters"))
        if dst.exists() and dst not in sources and dst != src:
            problems.append(Problem(dst, "target already exists"))
        if dst in planned_targets and planned_targets[dst] != src:
            problems.append(Problem(dst, f"two sources target this path: {planned_targets[dst].name} and {src.name}"))
        planned_targets[dst] = src

    return problems


def _ordered(operations: list[Operation]) -> list[Operation]:
    rank = {OpKind.MKDIR: 0, OpKind.MOVE: 1, OpKind.QUARANTINE: 2, OpKind.RMDIR: 3}
    return sorted(operations, key=lambda op: rank.get(op.kind, 9))


def execute(
    plan: Plan,
    run_id: str,
    *,
    operations: Optional[list[Operation]] = None,
    progress: Optional[Progress] = None,
    sweep_empty: bool = True,
    journal: Optional[Journal] = None,
) -> Result:
    operations = plan.selected_operations() if operations is None else operations
    result = Result(run_id=run_id)

    problems = preflight(plan, operations)
    if problems:
        result.failures = problems
        return result

    journal = journal or Journal(run_id)
    journal.open(plan.root, plan.preset)
    result.journal_path = journal.path
    made_dirs: set[Path] = set()

    try:
        ordered = _ordered(operations)
        total = len(ordered)
        for index, op in enumerate(ordered):
            if progress is not None and index % 10 == 0:
                progress("applying", index, total)
            try:
                if op.kind is OpKind.MKDIR:
                    if op.dst is not None and not op.dst.exists():
                        _mkdir_recorded(op.dst, journal, made_dirs)
                        result.folders_created += 1
                elif op.kind in (OpKind.MOVE, OpKind.QUARANTINE):
                    if op.src is None or op.dst is None:
                        continue
                    if op.dst.exists():
                        result.failures.append(Problem(op.dst, "target appeared during the run, skipped"))
                        continue
                    _mkdir_recorded(op.dst.parent, journal, made_dirs)
                    shutil.move(str(op.src), str(op.dst))
                    journal.record(op.kind.value, op.src, op.dst, op.size)
                    result.bytes_moved += op.size
                    if op.kind is OpKind.QUARANTINE:
                        result.quarantined += 1
                    else:
                        result.moved += 1
            except OSError as exc:
                result.failures.append(Problem(op.src, str(exc)))

        if sweep_empty:
            result.folders_removed = _sweep(plan.root, journal, result)
    finally:
        journal.close("complete" if result.ok else "complete-with-failures")

    return result


def _mkdir_recorded(directory: Path, journal: Journal, made: set[Path]) -> None:
    if directory in made or directory.exists():
        return
    missing = []
    current = directory
    while not current.exists():
        missing.append(current)
        current = current.parent
    for path in reversed(missing):
        path.mkdir(exist_ok=True)
        journal.record("mkdir", None, path)
        made.add(path)


def _sweep(root: Path, journal: Journal, result: Result) -> int:
    """Remove folders the run emptied. Only empties, never anything with content."""
    removed = 0
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        here = Path(dirpath)
        if here == root or QUARANTINE_DIRNAME in here.parts:
            continue
        try:
            if not any(here.iterdir()):
                here.rmdir()
                journal.record("rmdir", here, None)
                removed += 1
        except OSError as exc:
            result.failures.append(Problem(here, str(exc)))
    return removed


def undo(journal_path: Path, progress: Optional[Progress] = None) -> Result:
    """Replay a run backwards. Anything that no longer matches is reported, not forced."""
    records = [r for r in read_records(journal_path) if "seq" in r]
    records.sort(key=lambda r: r["seq"], reverse=True)
    result = Result(run_id=journal_path.stem, journal_path=journal_path)
    total = len(records)

    for index, record in enumerate(records):
        if progress is not None and index % 10 == 0:
            progress("undoing", index, total)
        op = record.get("op")
        src = Path(record["from"]) if record.get("from") else None
        dst = Path(record["to"]) if record.get("to") else None
        try:
            if op in ("move", "quarantine"):
                if dst is None or src is None:
                    continue
                if not dst.exists():
                    result.failures.append(Problem(dst, "file is no longer where the journal left it"))
                    continue
                if src.exists():
                    result.failures.append(Problem(src, "original path is occupied, left alone"))
                    continue
                src.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dst), str(src))
                result.moved += 1
                result.bytes_moved += record.get("size", 0)
            elif op == "mkdir":
                if dst is not None and dst.is_dir() and not any(dst.iterdir()):
                    dst.rmdir()
                    result.folders_removed += 1
            elif op == "rmdir":
                if src is not None and not src.exists():
                    src.mkdir(parents=True, exist_ok=True)
                    result.folders_created += 1
        except OSError as exc:
            result.failures.append(Problem(src or dst, str(exc)))

    return result
