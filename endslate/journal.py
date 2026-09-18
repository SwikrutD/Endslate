"""Append-only record of what the executor did, so any run can be reversed."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from endslate.config import runs_dir


@dataclass
class JournalRecord:
    seq: int
    op: str
    src: Optional[str]
    dst: Optional[str]
    size: int
    ts: str

    @classmethod
    def from_json(cls, data: dict) -> "JournalRecord":
        return cls(
            seq=data.get("seq", 0),
            op=data.get("op", ""),
            src=data.get("from"),
            dst=data.get("to"),
            size=data.get("size", 0),
            ts=data.get("ts", ""),
        )


@dataclass
class RunInfo:
    run_id: str
    path: Path
    started: str
    root: str
    preset: str
    operations: int
    closed: bool
    reverted: bool

    @property
    def label(self) -> str:
        state = "reverted" if self.reverted else ("complete" if self.closed else "interrupted")
        return f"{self.started}  {self.operations} ops  {state}"


class Journal:
    """One file per run. Header line, one line per operation, footer line."""

    def __init__(self, run_id: str, path: Optional[Path] = None):
        self.run_id = run_id
        self.path = path or (runs_dir() / f"{run_id}.jsonl")
        self._seq = 0
        self._handle = None

    def open(self, root: Path, preset: str) -> None:
        self._handle = open(self.path, "a", encoding="utf-8")
        self._write({
            "kind": "run",
            "run_id": self.run_id,
            "root": str(root),
            "preset": preset,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })

    def record(self, op: str, src: Optional[Path], dst: Optional[Path], size: int = 0) -> None:
        self._seq += 1
        self._write({
            "seq": self._seq,
            "op": op,
            "from": str(src) if src else None,
            "to": str(dst) if dst else None,
            "size": size,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })

    def close(self, status: str = "complete") -> None:
        if self._handle is None:
            return
        self._write({"kind": "end", "status": status, "operations": self._seq})
        self._handle.close()
        self._handle = None

    def _write(self, payload: dict) -> None:
        if self._handle is None:
            return
        self._handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._handle.flush()
        os.fsync(self._handle.fileno())


def read_records(path: Path) -> Iterator[dict]:
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue


def describe(path: Path) -> Optional[RunInfo]:
    header = None
    operations = 0
    closed = False
    reverted = False
    for record in read_records(path):
        kind = record.get("kind")
        if kind == "run":
            header = record
        elif kind == "end":
            closed = True
            reverted = record.get("status") == "reverted"
        elif "seq" in record:
            operations += 1
    if header is None:
        return None
    return RunInfo(
        run_id=header.get("run_id", path.stem),
        path=path,
        started=header.get("started", ""),
        root=header.get("root", ""),
        preset=header.get("preset", ""),
        operations=operations,
        closed=closed,
        reverted=reverted,
    )


def list_runs(directory: Optional[Path] = None) -> list[RunInfo]:
    directory = directory or runs_dir()
    out = []
    for path in sorted(directory.glob("*.jsonl"), reverse=True):
        info = describe(path)
        if info is not None:
            out.append(info)
    return out


def mark_reverted(path: Path) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"kind": "end", "status": "reverted"}) + "\n")
