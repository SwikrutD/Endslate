"""Plain-text rendering of a plan, used by the CLI and the tests."""
from __future__ import annotations

from pathlib import Path

from endslate.models import Bucket, OpKind, Plan

_ORDER = [Bucket.PLANNED, Bucket.NEEDS_YOU, Bucket.DUPLICATE, Bucket.JUNK, Bucket.SKIPPED, Bucket.NOOP]
_LABEL = {
    Bucket.PLANNED: "Planned",
    Bucket.NEEDS_YOU: "Needs you",
    Bucket.DUPLICATE: "Duplicates",
    Bucket.JUNK: "Junk",
    Bucket.SKIPPED: "Skipped",
    Bucket.NOOP: "Already correct",
}


def _rel(path, root: Path) -> str:
    if path is None:
        return "-"
    try:
        return str(Path(path).relative_to(root))
    except ValueError:
        return str(path)


def summary(plan: Plan) -> str:
    counts = plan.counts()
    bits = [f"{_LABEL[b]}: {counts[b.value]}" for b in _ORDER]
    moves = sum(1 for op in plan.selected_operations() if op.kind in (OpKind.MOVE, OpKind.QUARANTINE))
    bits.append(f"file operations: {moves}")
    return "  ".join(bits)


def render(plan: Plan, *, limit: int = 0, buckets: list[Bucket] | None = None) -> str:
    lines = [f"Library: {plan.root}", f"Preset:  {plan.preset}", "", summary(plan), ""]
    for bucket in buckets or _ORDER:
        entries = plan.by_bucket(bucket)
        if not entries:
            continue
        lines.append(f"== {_LABEL[bucket]} ({len(entries)}) " + "=" * 20)
        shown = entries if not limit else entries[:limit]
        for entry in shown:
            source = _rel(entry.source_path, plan.root)
            target = _rel(entry.target_path, plan.root)
            if bucket in (Bucket.PLANNED, Bucket.JUNK, Bucket.DUPLICATE):
                lines.append(f"  {source}")
                lines.append(f"    -> {target}" + (f"   [{entry.reason}]" if entry.reason else ""))
                for op in entry.ops:
                    if op.kind is OpKind.MOVE and entry.item is not None and op.src != entry.item.video.path:
                        lines.append(f"       + {_rel(op.src, plan.root)} -> {_rel(op.dst, plan.root)}")
            else:
                lines.append(f"  {source}" + (f"   [{entry.reason}]" if entry.reason else ""))
        if limit and len(entries) > limit:
            lines.append(f"  ... {len(entries) - limit} more")
        lines.append("")
    if plan.notes:
        lines.append("== Worth a look " + "=" * 20)
        for note in plan.notes:
            lines.append(f"  {note}")
    return "\n".join(lines)
